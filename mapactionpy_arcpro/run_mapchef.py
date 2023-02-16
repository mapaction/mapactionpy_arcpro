from os.path import isfile, join
import argparse
import os
from mapactionpy_controller.event import Event
# from mapactionpy_controller.map_recipe import MapRecipe
# from mapactionpy_controller.layer_properties import LayerProperties
# from mapactionpy_controller.map_cookbook import MapCookbook
from mapactionpy_arcpro.arcpro_runner import ArcProRunner
from mapactionpy_arcpro.arcpro_runner import MapChef
import json


def is_valid_file(parser, arg):
    if not os.path.exists(arg):
        parser.error("The file %s does not exist!" % arg)
        return False
    else:
        return arg

def is_valid_directory(parser, arg):
    if os.path.isdir(arg):
        return arg
    else:
        parser.error("The directory %s does not exist!" % arg)
        return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", dest="eventDescriptionFile", required=True,
                        help="path to file", metavar="FILE", type=lambda x: is_valid_file(parser, x))
    parser.add_argument("--mapnumber", dest="mapnumber", required=True, help="Map Number")
    parser.add_argument('--overwrite', dest="overwrite", action='store_true')

    args = parser.parse_args()

    event = Event(args.eventDescriptionFile)
    runner = ArcProRunner(event) 
    mapChef = MapChef(runner)

    mapChef.cook(args.mapnumber, args.overwrite)
    if args.overwrite == True:
        print("OVERWRITE = TRUE")
    else:
        print("OVERWRITE = FALSE")
    
if __name__ == '__main__':
    main()
