import json
import os
import sys

import pytest
from qgis.core import (
    Qgis,
    QgsFontMarkerSymbolLayer,
    QgsPalLayerSettings,
    QgsProject,
    QgsRasterMarkerSymbolLayer,
    QgsRuleBasedLabeling,
    QgsRuleBasedRenderer,
    QgsSimpleFillSymbolLayer,
    QgsSimpleLineSymbolLayer,
    QgsSymbol,
    QgsVectorTileBasicLabeling,
    QgsVectorTileBasicRendererStyle,
)
from qgis.PyQt.QtCore import QPointF
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import QApplication

from JMapCloud.core.services.files_manager import DatasourceManager
from JMapCloud.core.services.qgis_project_style_manager import QGISProjectStyleManager

ORGANIZATION_ID = "ABC123"
PROJECT_ID = "DEF456"
PROJECT_NAME = "project_unit_tests"
LANGUAGE = "fr"

OBJECT_MAP = {"QGISExpression": QGISProjectStyleManager.QGISExpression}

if not QApplication.instance():
    app = QApplication(sys.argv)


class Test_DatasourceManager:
    # setup
    def setup_method(self):
        self.datasource_manager = DatasourceManager({"organizationId": ORGANIZATION_ID, "accessToken": "token"})

    """
    def from_dict(d):
        if "__class__" in d:
            class_name = d.pop("__class__")  # get the class name
            if class_name in OBJECT_MAP:
                return OBJECT_MAP[class_name](**d)  # reconstruct the object
        return d 
    """

    with open("./test_data/Test_DatasourceManager_data.json", "r", encoding="utf-8") as file:
        TEST_DATA = json.load(file)
        # TEST_DATA = json.load(file,object_hook=from_dict)

    # class fixtures

    # tests method
    @pytest.mark.skip
    def test_create_datasource_from_geojson(self):
        pass

    @pytest.mark.parametrize(
        "data, expected",
        list(
            zip(TEST_DATA["test_qgis_typename_to_mysql"]["data"], TEST_DATA["test_qgis_typename_to_mysql"]["expected"])
        ),
    )
    def test_qgis_typename_to_mysql(self, data, expected):
        assert self.datasource_manager.qgis_typename_to_mysql(data) == expected


class Test_QGISProjectStyleManager:

    # setup
    def setup_method(self):
        self.project_style_manager = QGISProjectStyleManager(
            {"id": PROJECT_ID, "name": PROJECT_NAME, "language": LANGUAGE}, ORGANIZATION_ID
        )

    def from_dict(d):
        if "__class__" in d:
            class_name = d.pop("__class__")  # get the class name
            if class_name in OBJECT_MAP:
                return OBJECT_MAP[class_name](**d)  # reconstruct the object
        return d

    with open("./test_data/Test_QGISProjectStyleManager_data.json", "r", encoding="utf-8") as file:
        TEST_DATA = json.load(file, object_hook=from_dict)

    # class fixtures
    @pytest.fixture
    def mock_get_project_sprites(self, mocker):
        json_sprites_return_value = {
            "01590362-0caf-4188-bb06-2d85c56917c5": {"pixelRatio": 2, "y": 0, "x": 0, "width": 30, "height": 30},
            "073fbd19-c27c-4307-a8a8-b514a67833b8": {"pixelRatio": 2, "y": 30, "x": 0, "width": 30, "height": 30},
        }
        chemin_image = os.path.join(os.path.dirname(__file__), "test_data", "mapbox-sprite.png")
        with open(chemin_image, "rb") as file:
            images_sprite_return_value = file.read()

        mock_get_project_sprites = mocker.patch(
            "jmap.core.project_style_manager.JMapMCS.get_project_sprites",
            autospec=True,
            return_value=(json_sprites_return_value, images_sprite_return_value),
        )

        yield mock_get_project_sprites
        mocker.stopall()

    # tests method

    @pytest.mark.parametrize(
        "data, expected",
        list(zip(TEST_DATA["test_convert_mapbox_font"]["data"], TEST_DATA["test_convert_mapbox_font"]["expected"])),
    )
    def test_convert_mapbox_font(self, data, expected):
        assert self.project_style_manager._convert_mapbox_font(data) == tuple(expected)

    @pytest.mark.parametrize(
        "data, expected",
        list(zip(TEST_DATA["common"]["layer_data"], TEST_DATA["test_format_JMap_label_configs"]["expected"])),
    )
    def test_format_JMap_label_configs(self, data, expected):
        assert self.project_style_manager.format_JMap_label_configs(data) == expected

    @pytest.mark.parametrize(
        "data, expected",
        list(
            zip(
                TEST_DATA["test_format_styles"]["data"],
                TEST_DATA["common"]["formatted_style"],
            )
        ),
    )
    def test_format_styles(self, data, expected, mock_get_project_sprites):
        assert (
            self.project_style_manager.format_styles(data["mapboxStyle"], data["graphqlData"], data["labelingData"])
            == expected
        )
        assert mock_get_project_sprites.call_count == 1

    @pytest.mark.parametrize(
        "data, expected",
        list(zip(TEST_DATA["common"]["labeling_data"], TEST_DATA["test_get_layer_labels"]["expected"])),
    )
    def test_get_layer_labels(self, data, expected):
        labeling = self.project_style_manager.get_layer_labels(data)
        assert isinstance(labeling, QgsRuleBasedLabeling)
        root_rule = labeling.rootRule()

        assert len(root_rule.children()) == 1
        rule = root_rule.children()[0]
        assert rule.maximumScale() == expected["rule"]["maximumScale"]
        assert rule.minimumScale() == expected["rule"]["minimumScale"]
        assert rule.active() == expected["rule"]["active"]
        assert isinstance(rule.settings(), QgsPalLayerSettings)

    @pytest.mark.parametrize(
        "data, expected", list(zip(TEST_DATA["common"]["style_rule"], TEST_DATA["test_get_layer_styles"]["expected"]))
    )
    def test_get_layer_styles(self, data, expected):
        renderer = self.project_style_manager.get_layer_styles(data)

        assert isinstance(renderer, QgsRuleBasedRenderer)
        root_rule = renderer.rootRule()
        style_rules = root_rule.children()

        assert len(style_rules) == len(expected["styleRules"])
        for i, style_rule in enumerate(style_rules):
            style_rule_expected = expected["styleRules"][i]
            assert style_rule.label() == style_rule_expected["label"]

            rules = style_rule.children()
            assert len(rules) == len(style_rule_expected["rules"])
            for j, rule in enumerate(rules):
                rule_expected = style_rule_expected["rules"][j]
                assert isinstance(rule.symbol(), QgsSymbol)
                assert rule.label() == rule_expected["label"]
                assert rule.filterExpression() == rule_expected["filterExpression"]
                assert rule.maximumScale() == rule_expected["maximumScale"]
                assert rule.minimumScale() == rule_expected["minimumScale"]
                assert rule.active() == rule_expected["active"]

    @pytest.mark.parametrize(
        "common_data, data, expected",
        list(
            zip(
                TEST_DATA["common"]["labeling_data"],
                TEST_DATA["test_get_mvt_layer_labels"]["data"],
                TEST_DATA["test_get_mvt_layer_labels"]["expected"],
            )
        ),
    )
    def test_get_mvt_layer_labels(self, common_data, data, expected):
        labeling = self.project_style_manager.get_mvt_layer_labels(common_data, data["elementType"])
        assert isinstance(labeling, QgsVectorTileBasicLabeling)
        styles = labeling.styles()
        assert len(styles) == 1
        style = styles[0]
        assert style.geometryType() == Qgis.GeometryType[expected["elementType"]]
        assert style.minZoomLevel() == expected["rule"]["minimumZoom"]
        assert style.maxZoomLevel() == expected["rule"]["maximumZoom"]
        assert style.isEnabled() == expected["rule"]["active"]
        assert isinstance(style.labelSettings(), QgsPalLayerSettings)

    @pytest.mark.parametrize(
        "common_data,data, expected",
        list(
            zip(
                TEST_DATA["common"]["style_rule"],
                TEST_DATA["test_get_mvt_layer_styles"]["data"],
                TEST_DATA["test_get_mvt_layer_styles"]["expected"],
            )
        ),
    )
    def test_get_mvt_layer_styles(self, common_data, data, expected):
        styles_rules = self.project_style_manager.get_mvt_layer_styles(common_data, data["elementType"])
        for i, style_rules in enumerate(styles_rules):
            for j, rule in enumerate(style_rules["style_list"]):
                rule_expected = expected["styleRules"][i]["rules"][j]
                assert isinstance(rule, QgsVectorTileBasicRendererStyle)
                assert isinstance(rule.symbol(), QgsSymbol)
                assert rule.styleName() == rule_expected["label"]
                assert rule.filterExpression() == rule_expected["filterExpression"]
                assert rule.maxZoomLevel() == rule_expected["maxZoomLevel"]
                assert rule.minZoomLevel() == rule_expected["minZoomLevel"]
                assert rule.isEnabled() == rule_expected["active"]

    @pytest.mark.parametrize(
        "common_data, data, expected",
        list(
            zip(
                TEST_DATA["common"]["style_map_scale"],
                TEST_DATA["test_convert_t_map_scale_to_symbol"]["data"],
                TEST_DATA["test_convert_t_map_scale_to_symbol"]["expected"],
            )
        ),
    )
    def test_convert_t_map_scale_to_symbol(self, common_data, data, expected):
        self.project_style_manager.icons = data["icons"]
        symbol = self.project_style_manager._convert_t_map_scale_to_symbol(common_data)

        assert isinstance(symbol, QgsSymbol)

        symbol_layers = symbol.symbolLayers()
        assert len(symbol_layers) == len(expected["symbolLayers"])
        for i, symbol_layer in enumerate(symbol_layers):
            symbol_layer_expected = expected["symbolLayers"][i]
            if isinstance(symbol_layer, QgsSimpleFillSymbolLayer):

                pass
            elif isinstance(symbol_layer, QgsSimpleLineSymbolLayer):
                pass
            elif isinstance(symbol_layer, QgsRasterMarkerSymbolLayer):
                assert symbol_layer_expected["iconImage"] in symbol_layer.path()
                assert symbol_layer.size() == symbol_layer_expected["size"]
                assert symbol_layer.fixedAspectRatio() == symbol_layer_expected["fixedAspectRatio"]
                assert symbol_layer.offset() == QPointF(
                    symbol_layer_expected["offsetX"], symbol_layer_expected["offsetY"]
                )
                assert symbol_layer.sizeUnit() == Qgis.RenderUnit.Pixels
                properties = symbol_layer.dataDefinedProperties()
                assert properties.count() == len(symbol_layer_expected["customProperties"])
                # property1 = properties.property()
                # assert property1.expressionString() == symbol_layer_expected["property1ExpressionString"]
                # property1 = properties.property()
                # assert property1.expressionString() == symbol_layer_expected["property1ExpressionString"]

            elif isinstance(symbol_layer, QgsFontMarkerSymbolLayer):
                assert symbol_layer.fontFamily() == symbol_layer_expected["fontFamily"]
                assert symbol_layer.fontStyle() == symbol_layer_expected["fontStyle"]
                expected_color = QColor(symbol_layer_expected["textColor"])
                expected_color.setAlphaF(symbol_layer_expected["textOpacity"])
                assert symbol_layer.color().name() == expected_color.name()

            else:
                assert False

    @pytest.fixture
    def mock_qgs_project_attached_file(self, mocker):
        """isolated Fixture that mock QgsProject.createAttachedFile() and reset after each test."""
        real_project_instance = QgsProject.instance()
        mock_create_attached_file = mocker.patch.object(
            real_project_instance, "createAttachedFile", return_value="./chemin/random.png"
        )
        mocker.patch("qgis.core.QgsProject.instance", return_value=real_project_instance)

        yield mock_create_attached_file

        real_project_instance.clear()
        mocker.stopall()

    @pytest.mark.parametrize("expected", TEST_DATA["test_get_project_icons_from_sprite_sheet"]["expected"])
    def test_get_project_icons_from_sprite_sheet(
        self, expected, mock_qgs_project_attached_file, mock_get_project_sprites
    ):

        icons = self.project_style_manager._get_project_icons_from_sprite_sheet()
        mock_get_project_sprites.assert_called_once()
        assert mock_qgs_project_attached_file.call_count == 2
        assert icons == expected
