"""Evidence-backed E172-0225 syntax mapping; no semantic identity resolution."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, fields, replace
from typing import ClassVar, TypedDict

from sema_sedd.adapters._e172_0225_xml import XSI_NIL, Context, Reader, split_name
from sema_sedd.adapters.base import AdapterResult, DiagnosticSeverity, SupportLevel
from sema_sedd.adapters.revisions import detect_revision
from sema_sedd.exceptions import UnsupportedSeddVersionError
from sema_sedd.model import (
    Alarm,
    CanonicalType,
    CollectionEvent,
    DataStructure,
    DataVariable,
    DefaultReport,
    EntityReference,
    EquipmentConstant,
    EquipmentInterface,
    EquipmentMetadata,
    EventReportLink,
    JsonArray,
    JsonObject,
    MessageDirection,
    RemoteCommand,
    RemoteCommandParameter,
    Requiredness,
    SourceProvenance,
    StandardReference,
    StateTransition,
    StatusVariable,
    SupportedMessage,
    UnresolvedReason,
    UnresolvedReference,
    VariableFormat,
    WellKnownName,
)
from sema_sedd.parser import SourcedDocument
from sema_sedd.parser.ingest import XSI_NO_NAMESPACE_SCHEMA_LOCATION, XSI_SCHEMA_LOCATION

SEDD_NAMESPACE = "urn:semi-org:xsd.SEDD"
SEDD_ROOT = f"{{{SEDD_NAMESPACE}}}DataDictionary"

SMN = "urn:semi-org:xsd.SMN"
_VARIABLE_TYPES = (
    CanonicalType.STATUS_VARIABLE,
    CanonicalType.DATA_VARIABLE,
    CanonicalType.EQUIPMENT_CONSTANT,
)
_REQUIRED_SECTIONS = frozenset(
    (
        "CollectionEvents",
        "DataVariables",
        "StatusVariables",
        "EquipmentConstants",
        "Alarms",
        "VariableFormats",
    )
)
_ITEM_KINDS = {
    "LST": "list",
    "BIN": "bin",
    "BOO": "boo",
    "ASC": "asc",
    "JIS": "jis",
    "MBC": "mbc",
    "SI8": "si8",
    "SI1": "si1",
    "SI2": "si2",
    "SI4": "si4",
    "FP8": "fp8",
    "FP4": "fp4",
    "UI8": "ui8",
    "UI1": "ui1",
    "UI2": "ui2",
    "UI4": "ui4",
    "ANY": "any",
    "SET": "set",
    "SIA": "sia",
    "UIA": "uia",
    "INT": "int",
    "FPA": "fpa",
    "ENU": "enumeration",
    "BIT": "bit",
    "Format": "format_choice",
    "EnumFormat": "enum_format",
    "EnumerationChoices": "enum_choices",
    "EnumValue": "enum_value",
    "Value": "value",
    "Description": "description",
    "BitFieldFormat": "bit_field_format",
    "BitFieldDefinitions": "bit_field_definitions",
    "BitPosition": "bit_position",
    "BitNumber": "bit_number",
    "OnValue": "on_value",
    "OffValue": "off_value",
}
_COMPLIANCE_VALUES = frozenset(("Yes", "No", "C", "NC", "WC", "Partial", "NA"))
_BLOCKING_VALUES = frozenset(("M", "S"))
_REPLY_OPTION_VALUES = frozenset(("required", "optional", "never"))


class _CommonFields(TypedDict):
    key: str
    implementation_id: str | None
    name: str | None
    description: str | None
    declared_source: str | None
    wkn: WellKnownName | None
    standards: tuple[EntityReference, ...]
    provenance: tuple[SourceProvenance, ...]


def _reference(
    reader: Reader, name: str, kinds: tuple[CanonicalType, ...], *, by_name: bool = False
) -> EntityReference | None:
    node = reader.one(name)
    if node is None:
        return None
    return _reference_node(Reader(reader.context, node), kinds, by_name=by_name)


def _reference_node(
    reader: Reader, kinds: tuple[CanonicalType, ...], *, by_name: bool = False
) -> EntityReference:
    value = reader.leaf()
    label = reader.attribute("name")
    return EntityReference(
        target_types=kinds,
        implementation_id=None if by_name else value,
        name=value if by_name else label,
        provenance=(reader.context.provenance(reader.node, value),),
        unknown_extensions=reader.finish(),
    )


def _reference_list(
    reader: Reader, container: str, member: str, kinds: tuple[CanonicalType, ...]
) -> tuple[EntityReference, ...] | None:
    node = reader.one(container)
    if node is None:
        return None
    nested = Reader(reader.context, node)
    result = tuple(
        _reference_node(Reader(reader.context, child), kinds) for child in nested.many(member)
    )
    reader.retained.extend(nested.finish())
    return result


def _common(
    reader: Reader,
    identifier: str | None,
    name: str | None,
    *,
    description: str | None = "Description",
    decorated: bool = False,
) -> _CommonFields:
    native_id = reader.text(identifier, required=True) if identifier else None
    label = reader.text(name, required=True) if name else None
    wkn = None
    standard = None
    source = None
    if decorated:
        wkn_node = reader.one("WellKnownName")
        if wkn_node is not None:
            wkn_reader = Reader(reader.context, wkn_node)
            value = wkn_reader.leaf()
            if value is not None:
                wkn = WellKnownName(value=value, provenance=(reader.context.provenance(wkn_node),))
            reader.retained.extend(wkn_reader.finish())
        standard = _reference(
            reader, "SEMIStandard", (CanonicalType.STANDARD_REFERENCE,), by_name=True
        )
        source = reader.text("Source")
    return _CommonFields(
        key=reader.context.paths[id(reader.node)],
        implementation_id=native_id,
        name=label,
        description=reader.text(description) if description else None,
        declared_source=source,
        wkn=wkn,
        standards=(standard,) if standard else (),
        provenance=(reader.context.provenance(reader.node, native_id),),
    )


def _variable(
    reader: Reader, kind: CanonicalType
) -> StatusVariable | DataVariable | EquipmentConstant:
    constant = kind is CanonicalType.EQUIPMENT_CONSTANT
    identifier, label = {
        CanonicalType.STATUS_VARIABLE: ("SVID", "SVNAME"),
        CanonicalType.DATA_VARIABLE: ("VID", "DVVALNAME"),
        CanonicalType.EQUIPMENT_CONSTANT: ("ECID", "ECNAME"),
    }[kind]
    common = _common(reader, identifier, label, decorated=True)
    format_ref = _reference(reader, "Format", (CanonicalType.VARIABLE_FORMAT,), by_name=True)
    units = reader.texts("UNITS")
    minimum = reader.text("ECMIN" if constant else "MinValue")
    maximum = reader.text("ECMAX" if constant else "MaxValue")
    if constant:
        default = reader.text("ECDEF")
        return EquipmentConstant(
            **common,
            format=format_ref,
            units=units,
            minimum=minimum,
            maximum=maximum,
            default=default,
            unknown_extensions=reader.finish(),
        )
    cls = StatusVariable if kind is CanonicalType.STATUS_VARIABLE else DataVariable
    return cls(
        **common,
        format=format_ref,
        units=units,
        minimum=minimum,
        maximum=maximum,
        unknown_extensions=reader.finish(),
    )


def _status(reader: Reader) -> StatusVariable:
    result = _variable(reader, CanonicalType.STATUS_VARIABLE)
    assert isinstance(result, StatusVariable)
    return result


def _data(reader: Reader) -> DataVariable:
    result = _variable(reader, CanonicalType.DATA_VARIABLE)
    assert isinstance(result, DataVariable)
    return result


def _constant(reader: Reader) -> EquipmentConstant:
    result = _variable(reader, CanonicalType.EQUIPMENT_CONSTANT)
    assert isinstance(result, EquipmentConstant)
    return result


def _event(reader: Reader) -> CollectionEvent:
    common = _common(reader, "CEID", "CENAME", decorated=True)
    # A02 remains pending: do not assert target-kind restrictions for event VID lists.
    valid = _reference_list(reader, "VALIDDVS", "VID", ())
    relevant = _reference_list(reader, "RelevantVariables", "VID", ())
    transition = None
    node = reader.one("StateTransition")
    if node is not None:
        r = Reader(reader.context, node)
        transition = StateTransition(
            state_model=r.text("StateModel"),
            transition_id=r.text("TransitionID"),
            previous_state=r.text("PreviousState"),
            new_state=r.text("NewState"),
            provenance=(r.context.provenance(node),),
            unknown_extensions=r.finish(),
        )
    return CollectionEvent(
        **common,
        valid_data_variables=valid,
        relevant_variables=relevant,
        state_transition=transition,
        unknown_extensions=reader.finish(),
    )


def _alarm(reader: Reader) -> Alarm:
    return Alarm(
        **_common(reader, "ALID", "AlarmName", decorated=True),
        code=reader.integer("ALCD", minimum=-128, maximum=127),
        text=reader.text("ALTX"),
        set_event=_reference(reader, "SetEvent", (CanonicalType.COLLECTION_EVENT,)),
        clear_event=_reference(reader, "ClearEvent", (CanonicalType.COLLECTION_EVENT,)),
        unknown_extensions=reader.finish(),
    )


def _structure(reader: Reader, *, wrapper: bool = False) -> DataStructure:
    name = split_name(reader.node.tag)[1]
    kind = "sequence" if wrapper else _ITEM_KINDS[name]
    attrs = JsonObject(
        entries=tuple(
            (key, value)
            for key, value in reader.node.attributes
            if key
            in ("name", "id", "length", "description", "dataItemName", "maxLength", "minLength")
        )
    )
    reader.attributes.update(key for key, _ in attrs.entries)
    children = []
    for child in reader.node.children:
        namespace, local = split_name(child.tag)
        if namespace == SMN and local in _ITEM_KINDS:
            reader.consumed.add(id(child))
            children.append(_structure(Reader(reader.context, child)))
    value = "".join(part for part in reader.node.content if isinstance(part, str))
    if not reader.node.children:
        reader.body_used = True
    return DataStructure(
        kind=kind,
        name=reader.node.attribute("name"),
        description=reader.node.attribute("description"),
        value=value if value.strip(" \t\r\n") or not reader.node.children else None,
        attributes=attrs,
        children=tuple(children),
        provenance=(reader.context.provenance(reader.node),),
        unknown_extensions=reader.finish(),
    )


def _format_field(reader: Reader, name: str) -> tuple[DataStructure, ...] | None:
    node = reader.one(name)
    return (_structure(Reader(reader.context, node), wrapper=True),) if node is not None else None


def _format(reader: Reader) -> VariableFormat:
    return VariableFormat(
        **_common(reader, None, "FormatName", description=None),
        structure=_format_field(reader, "SECSData"),
        unknown_extensions=reader.finish(),
    )


def _parameter(reader: Reader) -> RemoteCommandParameter:
    common = _common(reader, None, "Name")
    label = reader.attribute("IsRequired")
    requiredness = None
    if label is not None:
        requiredness = {
            "Yes": Requiredness.YES,
            "No": Requiredness.NO,
            "Conditional": Requiredness.CONDITIONAL,
        }.get(label, Requiredness.UNKNOWN)
        if requiredness is Requiredness.UNKNOWN:
            reader.invalid("IsRequired", attribute=True)
    return RemoteCommandParameter(
        **common,
        requiredness=requiredness,
        value_format=_format_field(reader, "ValueFormat"),
        unknown_extensions=reader.finish(),
    )


def _command(reader: Reader) -> RemoteCommand:
    common = _common(reader, None, "Name", description="Documentation")
    parameters = None
    node = reader.one("AssociatedParameters")
    if node is not None:
        r = Reader(reader.context, node)
        parameters = tuple(
            _parameter(Reader(reader.context, child)) for child in r.many("Parameter")
        )
        reader.retained.extend(r.finish())
    return RemoteCommand(
        **common,
        parameters=parameters,
        object_specifiers=reader.texts("ObjectSpecifier"),
        use_s2f21=reader.boolean("useS2F21", attribute=True),
        use_s2f41=reader.boolean("useS2F41", attribute=True),
        use_s2f49=reader.boolean("useS2F49", attribute=True),
        unknown_extensions=reader.finish(),
    )


def _message(reader: Reader) -> SupportedMessage:
    common = _common(reader, None, None, description=f"{{{SMN}}}Description")
    label = reader.attribute("direction")
    direction = None
    if label is not None:
        direction = {
            "H to E": MessageDirection.HOST_TO_EQUIPMENT,
            "E to H": MessageDirection.EQUIPMENT_TO_HOST,
            "Both": MessageDirection.BOTH,
        }.get(label, MessageDirection.UNKNOWN)
        if direction is MessageDirection.UNKNOWN:
            reader.invalid("direction", attribute=True)
    structure_nodes = reader.many(f"{{{SMN}}}SECSData")
    common["name"] = reader.attribute("name")
    return SupportedMessage(
        **common,
        stream=reader.integer("s", attribute=True),
        function=reader.integer("f", attribute=True),
        direction=direction,
        mnemonic=reader.attribute("mnenomic"),
        reply_bit=reader.boolean("replyBit", attribute=True),
        reply_option=reader.enumeration("replyOption", _REPLY_OPTION_VALUES, attribute=True),
        blocking=reader.enumeration("blocking", _BLOCKING_VALUES, attribute=True),
        header=reader.text(f"{{{SMN}}}Header"),
        exceptions=reader.texts(f"{{{SMN}}}Exception"),
        structure=tuple(
            _structure(Reader(reader.context, node), wrapper=True) for node in structure_nodes
        )
        if structure_nodes
        else None,
        unknown_extensions=reader.finish(),
    )


def _report(reader: Reader) -> DefaultReport:
    return DefaultReport(
        **_common(reader, "RPTID", "DefaultReportName"),
        variables=_reference_list(reader, "VIDList", "VID", _VARIABLE_TYPES),
        unknown_extensions=reader.finish(),
    )


def _link(reader: Reader) -> EventReportLink:
    return EventReportLink(
        **_common(reader, None, None),
        event=_reference(reader, "CEID", (CanonicalType.COLLECTION_EVENT,)),
        reports=_reference_list(reader, "RPTIDList", "RPTID", (CanonicalType.DEFAULT_REPORT,)),
        unknown_extensions=reader.finish(),
    )


def _standard(reader: Reader) -> StandardReference:
    requirement_groups = []
    for group_node in reader.many("RequirementGroup"):
        group = Reader(reader.context, group_node)
        group_name = group.text("Name")
        requirements = []
        for requirement_node in group.many("Requirement"):
            requirement = Reader(reader.context, requirement_node)
            provenance = reader.context.provenance(requirement_node)
            requirements.append(
                JsonObject(
                    entries=(
                        ("name", requirement.text("Name")),
                        ("sections", JsonArray(items=requirement.texts("Section"))),
                        ("requirement_id", requirement.text("RequirementID")),
                        ("parent_requirement_id", requirement.text("ParentRequirementID")),
                        ("implemented", requirement.boolean("Implemented")),
                        ("compliant", requirement.enumeration("Compliant", _COMPLIANCE_VALUES)),
                        ("notes", JsonArray(items=requirement.texts("Note"))),
                        ("source_path", provenance.source_path),
                        ("line", provenance.line),
                        ("column", provenance.column),
                    )
                )
            )
            group.retained.extend(requirement.finish())
        provenance = reader.context.provenance(group_node)
        requirement_groups.append(
            JsonObject(
                entries=(
                    ("kind", "requirement_group"),
                    ("name", group_name),
                    ("requirements", JsonArray(items=tuple(requirements))),
                    ("source_path", provenance.source_path),
                    ("line", provenance.line),
                    ("column", provenance.column),
                )
            )
        )
        reader.retained.extend(group.finish())
    return StandardReference(
        **_common(reader, None, "SEMIStandardName", description=None),
        designation=reader.text("SEMIStandard"),
        requirements=tuple(requirement_groups),
        notes=reader.texts("Note"),
        unknown_extensions=reader.finish(),
    )


def _pending(interface: EquipmentInterface) -> tuple[UnresolvedReference, ...]:
    pending = []
    for entity in interface.entities():
        for member in fields(entity):
            value = getattr(entity, member.name)
            refs = (
                ((member.name, value),)
                if isinstance(value, EntityReference)
                else tuple(
                    (f"{member.name}[{index}]", item)
                    for index, item in enumerate(value)
                    if isinstance(item, EntityReference)
                )
                if isinstance(value, tuple)
                else ()
            )
            for relationship, ref in refs:
                reason = (
                    UnresolvedReason.NOT_ATTEMPTED
                    if ref.implementation_id or ref.name or ref.wkn
                    else UnresolvedReason.MISSING_SELECTOR
                )
                pending.append(
                    UnresolvedReference(
                        owner_key=entity.key,
                        relationship=relationship,
                        reference=ref,
                        reason=reason,
                        provenance=ref.provenance,
                    )
                )
    return tuple(pending)


@dataclass(frozen=True, slots=True)
class E172_0225Adapter:
    revision: ClassVar[str] = "E172-0225"

    def detect_support(self, document: SourcedDocument) -> SupportLevel:
        if document.namespace != SEDD_NAMESPACE or document.root.tag != SEDD_ROOT:
            return SupportLevel.UNSUPPORTED
        detection = detect_revision(document)
        if detection.revision_hint == self.revision:
            return SupportLevel.SUPPORTED
        if (
            detection.diagnostic_code == "MISSING_SCHEMA_HINT"
            and document.schema_location is None
            and document.root.attribute(XSI_NO_NAMESPACE_SCHEMA_LOCATION) is None
        ):
            return SupportLevel.INDETERMINATE
        return SupportLevel.UNSUPPORTED

    def parse(self, document: SourcedDocument) -> AdapterResult:
        support = self.detect_support(document)
        if support is SupportLevel.UNSUPPORTED:
            detection = detect_revision(document)
            label = detection.revision_hint
            detail = f"; detected schema hint: {label}" if label else ""
            raise UnsupportedSeddVersionError(
                f"Document is incompatible with E172-0225 adapter{detail}",
                detected_revision=label,
                diagnostic_code=detection.diagnostic_code or "UNSUPPORTED_REVISION",
            )
        context = Context(document, self.revision)
        context.diagnostic(
            "EXPLICIT_REVISION_SELECTION"
            if support is SupportLevel.INDETERMINATE
            else "REVISION_HINT_ONLY",
            "Adapter revision selected; schema conformance is not established",
            document.root,
            DiagnosticSeverity.INFO,
        )
        if (document.root.attribute(XSI_NIL) or "").strip(" \t\r\n") in ("true", "1"):
            context.diagnostic(
                "NIL_CONTENT", "Nil document retained without mapping", document.root
            )
            return AdapterResult(
                EquipmentInterface(
                    provenance=(context.provenance(document.root),),
                    unknown_extensions=(context.opaque(document.root, "nil_document"),),
                ),
                self.revision,
                tuple(context.diagnostics),
            )
        root = Reader(context, document.root)
        root.attribute(XSI_SCHEMA_LOCATION)
        header = root.one("SEDDHeader", required=True)
        equipment = EquipmentMetadata()
        if header is not None:
            r = Reader(context, header)
            equipment_id = r.text("EquipmentID")
            equipment = EquipmentMetadata(
                implementation_id=equipment_id,
                model=r.text("MDLN", required=True),
                software_revision=r.text("SOFTREV", required=True),
                supplier=r.text("Supplier"),
                created_date=r.text("CreateDate"),
                description=r.text("Description"),
                provenance=(context.provenance(header, equipment_id),),
                unknown_extensions=r.finish(),
            )
        deletion_flags: dict[str, bool | None] = {}

        def collect[T](section: str, item: str, mapper: Callable[[Reader], T]) -> tuple[T, ...]:
            node = root.one(section, required=section in _REQUIRED_SECTIONS)
            if node is None:
                return ()
            reader = Reader(context, node)
            if section in ("DefaultReportDefinitions", "DefaultEventReportLinks"):
                deletion_flags[section] = reader.boolean("CanBeDeleted")
            result = tuple(mapper(Reader(context, child)) for child in reader.many(item))
            root.retained.extend(reader.finish())
            return result

        interface = EquipmentInterface(
            equipment=equipment,
            provenance=(context.provenance(document.root),),
            status_variables=collect("StatusVariables", "StatusVariable", _status),
            data_variables=collect("DataVariables", "DataVariable", _data),
            equipment_constants=collect("EquipmentConstants", "EquipmentConstant", _constant),
            collection_events=collect("CollectionEvents", "CollectionEvent", _event),
            alarms=collect("Alarms", "Alarm", _alarm),
            remote_commands=collect("RemoteCommands", "RemoteCommand", _command),
            supported_messages=collect("SECSMessages", f"{{{SMN}}}SECSMessage", _message),
            variable_formats=collect("VariableFormats", "VariableFormat", _format),
            default_reports=collect("DefaultReportDefinitions", "DefaultReportDefinition", _report),
            event_report_links=collect("DefaultEventReportLinks", "EventReportLink", _link),
            standard_references=collect("SEMIStandards", "SupportedSEMIStandard", _standard),
            reports_can_be_deleted=deletion_flags.get("DefaultReportDefinitions"),
            event_report_links_can_be_deleted=deletion_flags.get("DefaultEventReportLinks"),
            unknown_extensions=root.finish(),
        )
        pending = _pending(interface)
        if pending:
            context.diagnostic(
                "REFERENCE_RESOLUTION_PENDING",
                "Reference selectors retained without resolution",
                document.root,
                DiagnosticSeverity.INFO,
            )
        return AdapterResult(
            replace(interface, unresolved_references=pending),
            self.revision,
            tuple(context.diagnostics),
        )
