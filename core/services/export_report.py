# -----------------------------------------------------------
# 2026-09-08
# Copyright (C) 2026 K2 Geospatial
# -----------------------------------------------------------
# Licensed under the terms of GNU GPL 3
# #
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
# -----------------------------------------------------------

from enum import Enum
from html import escape

from qgis.PyQt.QtCore import QObject


class LayerOutcome:
    class Status(Enum):
        exported = "EXPORTED"
        partially_exported = "PARTIALLY_EXPORTED"
        skipped = "SKIPPED"

    def __init__(self, layer_name: str):
        self.layer_name = layer_name
        self.status = LayerOutcome.Status.skipped
        self.reasons: list[str] = []

    def add_reason(self, reason: str):
        if reason and reason not in self.reasons:
            self.reasons.append(reason)


class ExportReport(QObject):
    class Scope(Enum):
        project = "PROJECT"
        layer = "LAYER"
        imported = "IMPORT"

    def __init__(self, scope: "ExportReport.Scope" = None):
        super().__init__()
        self.scope = scope or ExportReport.Scope.project
        self._outcomes: dict[str, LayerOutcome] = {}
        self.general_errors: list[str] = []
        self.project_name: str = None
        self.project_id: str = None
        self.aborted = False

    def register_layers(self, layer_names: list[str]):
        for layer_name in layer_names:
            self.outcome(layer_name)

    def outcome(self, layer_name: str) -> LayerOutcome:
        if layer_name not in self._outcomes:
            self._outcomes[layer_name] = LayerOutcome(layer_name)
        return self._outcomes[layer_name]

    def exported(self, layer_name: str):
        outcome = self.outcome(layer_name)
        if outcome.status == LayerOutcome.Status.skipped:
            outcome.status = LayerOutcome.Status.exported

    def partially_exported(self, layer_name: str, reason: str):
        outcome = self.outcome(layer_name)
        outcome.status = LayerOutcome.Status.partially_exported
        outcome.add_reason(reason)

    def skipped(self, layer_name: str, reason: str):
        outcome = self.outcome(layer_name)
        outcome.status = LayerOutcome.Status.skipped
        outcome.add_reason(reason)

    def note(self, message: str):
        """An error that cannot be attributed to one layer."""
        if message and message not in self.general_errors:
            self.general_errors.append(message)

    def has_issues(self) -> bool:
        return (
            self.aborted
            or len(self.general_errors) > 0
            or any(
                outcome.status != LayerOutcome.Status.exported
                for outcome in self._outcomes.values()
            )
        )

    def _by_status(self, status: LayerOutcome.Status) -> list[LayerOutcome]:
        return [outcome for outcome in self._outcomes.values() if outcome.status == status]

    def to_html(self) -> str:
        exported = self._by_status(LayerOutcome.Status.exported)
        partially = self._by_status(LayerOutcome.Status.partially_exported)
        skipped = self._by_status(LayerOutcome.Status.skipped)

        importing = self.scope == ExportReport.Scope.imported
        html = self._header_html(len(exported), len(partially), len(skipped))
        html += self._group_html(
            (
                self.tr("Partially loaded ({})")
                if importing
                else self.tr("Partially exported ({})")
            ).format(len(partially)),
            (
                self.tr("loaded in QGIS, but part of the style could not be imported")
                if importing
                else self.tr("in JMap Cloud, but part of the style could not be exported")
            ),
            partially,
        )
        html += self._group_html(
            self.tr("Skipped ({})").format(len(skipped)),
            (
                self.tr("not loaded in QGIS")
                if importing
                else self.tr("not present in the JMap Cloud project")
            ),
            skipped,
        )
        if len(self.general_errors) > 0:
            html += "<h4>{}</h4>".format(self.tr("Other errors"))
            for error in self.general_errors:
                html += "<p>{}</p>".format(escape(error).replace("\n", "<br>"))
        html += self._project_html()
        return html

    def _header_html(self, exported: int, partially: int, skipped: int) -> str:
        if self.scope == ExportReport.Scope.layer:
            return self._layer_header_html()
        total = exported + partially + skipped
        if self.scope == ExportReport.Scope.imported:
            return self._import_header_html(exported, partially, skipped, total)
        if self.aborted:
            return "<h3>{}</h3>".format(self.tr("Project exportation failed"))
        if not self.has_issues():
            return "<h3>{}</h3><p>{}</p>".format(
                self.tr("Project exportation finished"),
                self.tr("{} layers exported").format(total),
            )
        return "<h3>{}</h3><p>{}</p>".format(
            self.tr("Project exported with issues"),
            self.tr("{} layers: {} exported, {} partially exported, {} skipped").format(
                total, exported, partially, skipped
            ),
        )

    def _import_header_html(self, exported: int, partially: int, skipped: int, total: int) -> str:
        if self.aborted:
            return "<h3>{}</h3>".format(self.tr("Project importation failed"))
        if not self.has_issues():
            return "<h3>{}</h3><p>{}</p>".format(
                self.tr("Project loaded successfully"),
                self.tr("{} layers loaded").format(total),
            )
        return "<h3>{}</h3><p>{}</p>".format(
            self.tr("Project loaded with issues"),
            self.tr("{} layers: {} loaded, {} partially loaded, {} skipped").format(
                total, exported, partially, skipped
            ),
        )

    def _layer_header_html(self) -> str:
        if self.aborted:
            return "<h3>{}</h3>".format(self.tr("Layer exportation failed"))
        if not self.has_issues():
            return "<h3>{}</h3>".format(self.tr("Layer exportation finished"))
        return "<h3>{}</h3>".format(self.tr("Layer exported with issues"))

    def _group_html(self, title: str, subtitle: str, outcomes: list[LayerOutcome]) -> str:
        if len(outcomes) == 0:
            return ""
        # A single-layer report has nothing to count, so the group title says nothing
        # the header has not already said.
        html = "" if self.scope == ExportReport.Scope.layer else "<h4>{}</h4>".format(title)
        html += "<p><i>{}</i></p><ul>".format(subtitle)
        for outcome in sorted(outcomes, key=lambda outcome: outcome.layer_name):
            html += "<li><b>{}</b>".format(escape(outcome.layer_name))
            if len(outcome.reasons) > 0:
                html += " — {}".format(escape(", ".join(outcome.reasons)))
            html += "</li>"
        return html + "</ul>"

    def _project_html(self) -> str:
        if not self.project_id:
            return ""
        if self.aborted:
            message = self.tr(
                "An incomplete project was created in JMap Cloud: {} (id {}). "
                "You may want to delete it."
            )
        else:
            message = self.tr("Project created in JMap Cloud: {} (id {})")
        return "<p>{}</p>".format(
            escape(message.format(self.project_name or "", self.project_id))
        )
