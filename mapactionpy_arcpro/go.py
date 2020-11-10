import argparse
import os
from mapactionpy_controller.event import Event
from mapactionpy_controller.map_recipe import MapRecipe
from mapactionpy_controller.layer_properties import LayerProperties
from arcpro_runner import ArcProRunner


def is_valid_file(parser, arg):
    if not os.path.exists(arg):
        parser.error('The file "%s" does not exist!' % arg)
    else:
        return arg


def main(args):
    args = parser.parse_args()
    event = Event(args.eventDescriptionFile)
    runner = ArcProRunner(event)

    recipe_without_positive_iso3_code = (
        '''{
            "mapnumber": "MA001",
            "category": "Reference",
            "product": "DJI Overview Map",
            "summary": "Overview of DJI with topography displayed",
            "export": true,
            "template": "reference",
            "map_frames": [
                {
                    "name": "Main map",
                    "layers": [
                        {
                            "name": "mainmap-stle-stl-pt-s0-allmaps",
                            "reg_exp": "^[a-z][a-z][a-z]_stle_stl_pt_(.*?)_(.*?)_([phm][phm])(.*?).shp$",
                            "schema_definition": "stle_ste_pt.yml",
                            "definition_query": "fclass IN ('national_capital', 'city', 'capital', 'town')",
                            "display": true,
                            "add_to_legend": true,
                            "label_classes": [
                                {
                                    "class_name": "National Capital",
                                    "expression": "[name]",
                                    "sql_query": "('fclass' = 'national_capital')",
                                    "show_class_labels": true
                                },
                                {
                                    "class_name": "Admin 1 Capital",
                                    "expression": "[name]",
                                    "sql_query": "('fclass' = 'town')",
                                    "show_class_labels": true
                                }
                            ]
                        },
                        {
                            "name": "mainmap-carto-fea-py-s0-allmaps",
                            "reg_exp": "^[a-z][a-z][a-z]_carto_fea_py_(.*?)_(.*?)_([phm][phm])(.*?).shp$",
                            "schema_definition": "null-schema.yml",
                            "definition_query": "",
                            "display": true,
                            "add_to_legend": false,
                            "label_classes": []
                        },
                        {
                            "name": "mainmap-elev-cst-ln-s0-allmaps",
                            "reg_exp": "^[a-z][a-z][a-z]_elev_cst_ln_(.*?)_(.*?)_([phm][phm])(.*?).shp$",
                            "schema_definition": "null-schema.yml",
                            "definition_query": "",
                            "display": true,
                            "add_to_legend": false,
                            "label_classes": []
                        },
                        {
                            "name": "mainmap-admn-ad0-ln-s0-reference",
                            "reg_exp": "^[a-z][a-z][a-z]_admn_ad0_ln_(.*?)_(.*?)_([phm][phm])(.*?).shp$",
                            "schema_definition": "null-schema.yml",
                            "definition_query": "",
                            "display": true,
                            "add_to_legend": false,
                            "label_classes": []
                        },
                        {
                            "name": "mainmap-admn-ad1-ln-s0-reference",
                            "reg_exp": "^[a-z][a-z][a-z]_admn_ad1_ln_(.*?)_(.*?)_([phm][phm])(.*?).shp$",
                            "schema_definition": "admin1_reference.yml",
                            "definition_query": "",
                            "display": true,
                            "add_to_legend": true,
                            "label_classes": []
                        },
                        {
                            "name": "mainmap-phys-riv-ln-s0-reference",
                            "reg_exp": "^[a-z][a-z][a-z]_phys_riv_ln_(.*?)_(.*?)_([phm][phm])(.*?).shp$",
                            "schema_definition": "null-schema.yml",
                            "definition_query": "",
                            "display": true,
                            "add_to_legend": true,
                            "label_classes": []
                        },
                        {
                            "name": "mainmap-admn-ad1-py-s0-reference",
                            "reg_exp": "^[a-z][a-z][a-z]_admn_ad1_py_(.*?)_(.*?)_([phm][phm])(.*?).shp$",
                            "schema_definition": "admin1_reference.yml",
                            "definition_query": "",
                            "display": true,
                            "add_to_legend": true,
                            "label_classes": []
                        },
                        {
                            "name": "mainmap-admn-ad0-ln-s0-surroundingcountries",
                            "reg_exp": "^[a-z][a-z][a-z]_admn_ad0_ln_(.*?)_(.*?)_([phm][phm])(.*?).shp$",
                            "schema_definition": "null-schema.yml",
                            "definition_query": "",
                            "display": true,
                            "add_to_legend": true,
                            "label_classes": []
                        }
                    ]
                }
            ]
        }'''
    )

    layerProperties = LayerProperties(event.cmf_descriptor_path, '.lyr', verify_on_creation=False)
    recipe = MapRecipe(recipe_without_positive_iso3_code, layerProperties)
    recipe = runner.get_templates(state=recipe)
    recipe = runner.create_ouput_map_project(state=recipe)
    recipe = runner.build_project_files(state=recipe)

    themes = set()
    themes.add("Health")
    propertiesDict = {}
    propertiesDict['themes'] = themes
    propertiesDict['accessnotes'] = "My super access note"
    recipe = runner.export_maps(state=recipe, properties=propertiesDict)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Executes ArcProRunner for a given event',
    )
    parser.add_argument("--event", dest="eventDescriptionFile", required=True,
                        help="path to file", metavar="FILE", type=lambda x: is_valid_file(parser, x))
    args = parser.parse_args()
    main(args)
