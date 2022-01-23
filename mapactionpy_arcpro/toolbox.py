import argparse
import os
from mapactionpy_controller.event import Event
from mapactionpy_controller.map_recipe import MapRecipe
from mapactionpy_controller.layer_properties import LayerProperties
from arcpro_runner import ArcProRunner
import json


def is_valid_file(parser, arg):
    if not os.path.exists(arg):
        parser.error('The file "%s" does not exist!' % arg)
    else:
        return arg


def main(args):
    args = parser.parse_args()
    event = Event(args.eventDescriptionFile)
    runner = ArcProRunner(event)

    if args.projection == "none":
        args.projection = None

    recipeObject = {
            "mapnumber": args.mapNumber,
            "category": "Reference",
            "product": args.productTitle,
            "summary": "not set",  # this value is taken from the text element
            "export": True,
            "template": "reference",
            "version_num": args.versionNumber,
            "map_frames": [
                {
                    "name": "Main map",
                    "layers": []
                }
            ]
            }

    recipeJson = json.dumps(recipeObject)

    layerProperties = LayerProperties(event.cmf_descriptor_path, '.lyr', verify_on_creation=False)
    recipe = MapRecipe(recipeJson, layerProperties)
    recipe.map_project_path = args.projectFile

    setThemes = set()
    if (args.themesPipeSeparated != "none"):
        parts = args.themesPipeSeparated.split("|")
        for theme in parts:
            setThemes.add(theme)

    propertiesDict = {}
    propertiesDict['themes'] = setThemes
    propertiesDict['accessnotes'] = args.accessNotes
    propertiesDict['scale'] = args.scale
    if args.emfdpi == "0":
        propertiesDict['exportemf'] = False
    else:
        propertiesDict['exportemf'] = True
        propertiesDict['emfresolutiondpi'] = args.emfdpi
    propertiesDict['jpgresolutiondpi'] = args.jpegdpi
    propertiesDict['pdfresolutiondpi'] = args.pdfdpi
    propertiesDict['proj'] = args.projection
    propertiesDict['exportDirectory'] = args.exportDirectory
    propertiesDict['product-type'] = args.productType
    propertiesDict['mapBookMode'] = args.mapBookMode
    propertiesDict['layout'] = args.layout
    propertiesDict['status'] = args.status
    propertiesDict['location'] = args.location
    propertiesDict['qclevel'] = args.qclevel
    propertiesDict['access'] = args.access
    propertiesDict['countries'] = args.countries
    recipe.export_metadata = propertiesDict
    recipe = runner.export_maps(state=recipe)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Executes ArcProRunner for a given event',
    )
    parser.add_argument("--exportDirectory", dest="exportDirectory", required=True,
                        help="path to export folder")
    parser.add_argument("--event", dest="eventDescriptionFile", required=True,
                        help="path to file", metavar="FILE", type=lambda x: is_valid_file(parser, x))
    parser.add_argument("--mapNumber", dest="mapNumber", required=True, help="Map number")
    parser.add_argument("--projectFile", dest="projectFile", required=True,
                        help="path to aprx project file", metavar="FILE", type=lambda x: is_valid_file(parser, x))
    parser.add_argument("--layout", dest="layout", required=True, help="Layout name")
    parser.add_argument("--productTitle", dest="productTitle", required=True, help="Product title")
    parser.add_argument("--versionNumber", dest="versionNumber", required=True, help="Map version")
    parser.add_argument("--themesPipeSeparated", dest="themesPipeSeparated", required=True,
                        help="Themes pipe separated")
    parser.add_argument("--accessNotes", dest="accessNotes", help="Access Notes")
    parser.add_argument("--scale", dest="scale", required=True, help="Scale")
    parser.add_argument("--emfdpi", dest="emfdpi", required=True, help="nudEmfResolution")
    parser.add_argument("--jpegdpi", dest="jpegdpi", required=True, help="nudJpegResolution")
    parser.add_argument("--pdfdpi", dest="pdfdpi", required=True, help="nudPdfResolution")
    parser.add_argument("--projection", dest="projection", required=True, help="projection")
    parser.add_argument("--productType", dest="productType", required=True, help="type")
    parser.add_argument("--mapBookMode", dest="mapBookMode", required=True, help="mode")
    parser.add_argument("--status", dest="status", required=True, help="status")
    parser.add_argument("--qclevel", dest="qclevel", required=True, help="qcControl")
    parser.add_argument("--location", dest="location", required=True, help="location")
    parser.add_argument("--access", dest="access", required=True, help="access")
    parser.add_argument("--countries", dest="countries", required=True, help="countries")
    args = parser.parse_args()
    main(args)
