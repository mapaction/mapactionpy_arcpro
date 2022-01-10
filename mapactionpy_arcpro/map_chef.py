import os
import arcpy
import jsonpickle
import logging
import re
from datetime import datetime
import pytz
from pprint import pprint

# TODO asmith 2020/03/06
# What is the separation of responsiblities between MapChef and ArcProRunner? Why is the boundary
# between the two classes where it is? If I was to add a new function how would I know whether it
# should be added to MapChef or ArcProRunner?
#
# Is it intended that the `cook()` method might be called multiple times in the life of a MapChef
# object? At present it looks to me like `cook()` can only be called once. In which case why have
# `cook()` as a public method and why not call it directly from the constructor.


ESRI_DATASET_TYPES = [
    "SHAPEFILE_WORKSPACE",
    "RASTER_WORKSPACE",
    "FILEGDB_WORKSPACE",
    "ACCESS_WORKSPACE",
    "ARCINFO_WORKSPACE",
    "CAD_WORKSPACE",
    "EXCEL_WORKSPACE",
    "OLEDB_WORKSPACE",
    "PCCOVERAGE_WORKSPACE",
    "SDE_WORKSPACE",
    "TEXT_WORKSPACE",
    "TIN_WORKSPACE",
    "VPF_WORKSPACE"
]


def get_map_scale(arc_aprx, recipe):
    """
    Returns a human-readable string representing the map scale of the
    principal map frame of the mxd.

    @param arc_mxd: The MapDocument object of the map being produced.
    @param recipe: The MapRecipe object being used to produced it.
    @returns: The string representing the map scale.
    """

    scale_str = ""
    lyt = arc_aprx.listLayouts("*")[0]
    data_frames = lyt.listElements("MAPFRAME_ELEMENT", recipe.principal_map_frame)
    for df in data_frames:
        intValue = '{:,}'.format(int(df.camera.scale))
        scale_str = "1: " + intValue + " (At A3)"
        break
    return scale_str


def get_map_spatial_ref(arc_aprx, recipe):
    """
    Returns a human-readable string representing the spatial reference used to display the
    principal map frame of the mxd.

    @param arc_mxd: The MapDocument object of the map being produced.
    @param recipe: The MapRecipe object being used to produced it.
    @returns: The string representing the spatial reference. If the spatial reference cannot be determined
                then the value "Unknown" is returned.
    """
    layouts = arc_aprx.listLayouts("*")
    # for d in layouts[0].listElements("MAPFRAME_ELEMENT",'*') :
    #     print(d.name)
    data_frames = layouts[0].listElements("MAPFRAME_ELEMENT", recipe.principal_map_frame +"*")

    if not data_frames:
        err_msg = 'APRX does not have a MapFrame (aka DataFrame) with the name "{}"'.format(
            recipe.principal_map_frame)
        raise ValueError(err_msg)

    if len(data_frames) > 1:
        err_msg = 'APRX has more than one MapFrames (aka DataFrames) with the name "{}"'.format(
            recipe.principal_map_frame)
        raise ValueError(err_msg)

    df = data_frames.pop()
    spatial_ref_str = "Unknown"

    if (len(df.map.spatialReference.datumName) > 0):
        spatial_ref_str = df.map.spatialReference.datumName
        spatial_ref_str = spatial_ref_str[2:]
        spatial_ref_str = spatial_ref_str.replace('_', ' ')

    return spatial_ref_str


class MapChef:
    """
    Worker which creates a Map based on a predefined "recipe" from a cookbook
    """
    # TODO asmith 2020/03/06
    # This constructor seem unnecessarily complicated. In the ArcProRunner these objects are already
    # created:
    #   * MapCookbook object,
    #   * CrashMoveFolder object
    #   * LayerProperties object
    #   * Event object
    # It is already known that the various file and directory paths are valid etc. Why not just pass
    # those objects in as parameters to the MapChef constructor?
    #
    # Depending on whether or not it is indented that the `cook()` method might be called multiple
    # times in the life of a MapChef object, it would be worth reviewing

    def __init__(self,
                 aprx,
                 crashMoveFolder,
                 eventConfiguration):
        """
        Arguments:
           mxd {MXD file} -- MXD file.
           crashMoveFolder {CrashMoveFolder} -- CrashMoveFolder Object
           eventConfiguration {Event} -- Event Object
        """
        # TODO asmith 2020/03/06
        # See comment on the `cook()` method about where and when the `mxd` parameter should be
        # passed.
        self.aprx = aprx
        self.crashMoveFolder = crashMoveFolder

        self.eventConfiguration = eventConfiguration
        # self.cookbook = cookbook
        self.legendEntriesToRemove = list()

        self.replaceDataSourceOnly = False
        # It appears that this is not used - therefore should be removed. If it is used, then it
        # TODO asmith 2020/03/06
        # needs a more specific name. There exist Data, Layerfile, MXD and Template Naming
        # Conventions (and possibly more)
        self.namingConvention = None

        self.dataSources = set()
        self.createDate = datetime.utcnow().strftime("%d-%b-%Y")
        self.createTime = datetime.utcnow().strftime("%H:%M")
        self.export = False

    def disableLayers(self):
        """
        Makes all layers invisible for all data-frames
        """
        for m in self.aprx.listMaps("*"):
            for lyr in m.listLayers():
                lyr.visible = False

    def scale(self):
        newScale = ""
        lyt = self.aprx.listLayouts("*")[0]
        data_frames = lyt.listElements("MAPFRAME_ELEMENT", "*Main map*")
        print("--------Scale Level ----- ",len(data_frames))
        for df in data_frames:
            # pprint(df.camera)
            pprint(df.name)
            intValue = '{:,}'.format(int(df.camera.scale))
            newScale = "1: " + intValue + " (At A3)"
            break

        return newScale
    def spatialReference(self):
        spatialReferenceString = "Unknown"
        lyt = self.aprx.listLayouts("*")[0]

        for df in lyt.listElements("MAPFRAME_ELEMENT", "Main map*"):
            # if (len(df.spatialReference.datumName) > 0):
            #     spatialReferenceString = df.spatialReference.datumName
            #     spatialReferenceString = spatialReferenceString[2:]
            #     spatialReferenceString = spatialReferenceString.replace('_', ' ')
            break
        return spatialReferenceString

    # TODO asmith 2020/0306
    # Do we need to accommodate a use case where we would want to add layers but not make them
    # visible? If so is this something that we deal with when we get to it?
    def enableLayers(self):
        """
        Makes all layers visible for all data-frames
        """
        for m in self.aprx.listMaps("*"):
            for lyr in m.listLayers():
                lyr.visible = True

    def removeLayers(self):
        """
        Removes all layers for all data-frames
        """

        for m in self.aprx.listMaps("*"):
            for lyr in m.listLayers():
                if (lyr.longName != "Data Driven Pages"):
                    # arcpy.mp.RemoveLayer(lyr)*
                    pass 

        self.aprx.save()

    # TODO asmith 2020/03/06
    # I would suggest that:
    #   * If `cook()` only gets called once in the life of a MapChef object, then it should be
    #     entire procedural, with no parameters (everything set via the constructor) and
    #     subsequent attempt to call `cook()` should result in an exception
    #   * If `cook()` can be called multiple times, then the `mxd` and the `map_version_number`
    #     should be parameters for the cook method and not for the constructor.
    def cook(self, recipe):
        self.recipe = recipe
        arcpy.env.addOutputsToMap = False

        self.disableLayers()
        self.removeLayers()

        # self.mapReport = MapReport(recipe.product)
        if (self.recipe is not None):
            if len(self.recipe.summary):
                self.summary = self.recipe.summary
            for mf in self.recipe.map_frames:
                for layer in mf.layers:
                    print("process layer call in coock()", layer.name + "/" + mf.name)
                    self.process_layer(layer, mf)

        self.zoomToCountry()

        # Do things at a map layout level
        self.enableLayers()
        # arcpy.RefreshTOC()
        # arcpy.RefreshActiveView()
        arcpy.env.addOutputsToMap = True
        # self.showLegendEntries()
        self.aprx.save()

        if (recipe is not None):
            self.updateTextElements()
            self.aprx.save()
            
    def report_as_json(self):
        """
        Returns map report in json format
        """
        return(jsonpickle.encode(self.mapReport, unpicklable=False))

    def process_layer(self, recipe_lyr, arc_data_frame):
        """
        Updates or Adds a layer of data.  Maintains the Map Report.
        """
        # Try just using add Layer (currently no update layer option)
        print(f"Processing Layer {recipe_lyr.name}")
        self.addLayer(recipe_lyr, arc_data_frame)

    """
    Updates Text Elements in Marginalia

    """
    def updateTextElements(self):
        lyt = self.aprx.listLayouts()[0]

        for elm in lyt.listElements("TEXT_ELEMENT"):
            if elm.name == "country":
                elm.text = self.eventConfiguration.country_name
            if elm.name == "title":
                elm.text = self.recipe.product
            if elm.name == "create_date_time":
                elm.text = self.createDate + " " + self.createTime
            if elm.name == "summary":
                elm.text = self.summary
            if elm.name == "map_no":
                versionNumberString = "v" + str(self.recipe.version_num).zfill(2)
                elm.text = self.recipe.mapnumber + " " + versionNumberString
            if elm.name == "mxd_name":
                elm.text = os.path.basename(self.aprx.filePath)
            if elm.name == "scale":
                elm.text = self.scale()
            if elm.name == "data_sources":
                iter = 0
                dataSourcesString = "<BOL>Data Sources:</BOL>" + os.linesep + os.linesep
                for ds in self.dataSources:
                    if (iter > 0):
                        dataSourcesString = dataSourcesString + ", "
                    dataSourcesString = dataSourcesString + ds
                    iter = iter + 1
                elm.text = dataSourcesString
            if elm.name == "spatial_reference":
                elm.text = self.spatialReference()
            if elm.name == "glide_no":
                if self.eventConfiguration and self.eventConfiguration.glide_number:
                    elm.text = self.eventConfiguration.glide_number
            if elm.name == "donor_credit":
                if (self.eventConfiguration is not None):
                    elm.text = self.eventConfiguration.default_donor_credits
            if elm.name == "disclaimer":
                if (self.eventConfiguration is not None):
                    elm.text = self.eventConfiguration.default_disclaimer_text
            if elm.name == "map_producer":
                if (self.eventConfiguration is not None):
                    elm.text = "Produced by " + \
                        self.eventConfiguration.default_source_organisation + \
                        os.linesep + \
                        self.eventConfiguration.deployment_primary_email + \
                        os.linesep + \
                        self.eventConfiguration.default_source_organisation_url
        self.aprx.save()

    def showLegendEntries(self):
        for legend in self.aprx.listLayouts("*")[0].listElements("LEGEND_ELEMENT","*"):
            layerNames = list()
            for lyr in legend.listLegendItemLayers():
                if ((lyr.name in self.legendEntriesToRemove) or (lyr.name in layerNames)):
                    legend.removeItem(lyr)
                else:
                    layerNames.append(lyr.name)
        self.aprx.save()

    # TODO asmith 2020/03/06
    # Please don't hard code size and location of elements on the template
    # def alignLegend(self, orientation):
    def alignLegend(self):
        # for legend in arcpy.mapping.ListLayoutElements(self.aprx, "LEGEND_ELEMENT"):
        lyts = self.aprx.listLayouts("*")[0]
        for legend in lyts.listElements("LEGEND_ELEMENT","*"):
            if lyts.orientation == "landscape":
                # Resize
                legend.elementWidth = 60
                legend.elementPositionX = 248.9111
                legend.elementPositionY = 40
        self.aprx.save()

    # TODO asmith 2020/03/06
    # Please don't hard code size and location of elements on the template
    def resizeScaleBar(self):
        elm = arcpy.mapping.ListLayoutElements(self.aprx, "MAPSURROUND_ELEMENT", "Scale Bar")[0]
        elm.elementWidth = 51.1585
        self.aprx.save()

    def apply_frame_crs_and_extent(self, arc_data_frame, recipe_frame):
        """
        """
        # minx, miny, maxx, maxy = recipe_frame.extent
        # First set the spatial reference
        if not recipe_frame.crs[:5].lower() == 'epsg:':
            raise ValueError('unrecognised `recipe_frame.crs` value "{}". String does not begin with "EPSG:"'.format(
                recipe_frame.crs))

        prj_wkid = int(recipe_frame.crs[5:])
        arc_data_frame.spatialReference = arcpy.SpatialReference(prj_wkid)

        if recipe_frame.extent:
            new_extent = arcpy.Extent(*recipe_frame.extent)
            arc_data_frame.extent = new_extent
        self.aprx.save()

    def addLayer(self, recipe_lyr, recipe_frame):
        # addLayer(recipe_lyr, recipe_lyr.layer_file_path, recipe_lyr.name)
        # mapResult = MapResult(recipe_lyr.name)
        logging.debug('Attempting to add layer; {}'.format(recipe_lyr.layer_file_path))
        arc_lyr_to_add = arcpy.mp.LayerFile(recipe_lyr.layer_file_path)
        # if (".gdb/" not in recipe_lyr.reg_exp):
        #     mapResult = self.addLayerWithFile(recipe_lyr, arc_lyr_to_add,  recipe_frame)
        # else:
        #     mapResult = self.addLayerWithGdb(recipe_lyr, arc_lyr_to_add,  recipe_frame)

        # Apply Label Classes
        pprint("in addLayer function ")
        try:
            arc_layer = arc_lyr_to_add.listLayers(recipe_lyr.name)[0]
            self.apply_layer_visiblity(arc_layer, recipe_lyr)
            self.apply_label_classes(arc_layer, recipe_lyr)
            # Apply Definition Query
            self.apply_definition_query(arc_layer, recipe_lyr)
            # pprint("attempting to call addLayerWithFile")
            self.addLayerWithFile(arc_layer, recipe_lyr, recipe_frame)
            recipe_lyr.success = True
        except Exception as e :
            # print("cant reach addLayerWithFile")
            # pprint(e)
            recipe_lyr.success = False

    def apply_layer_visiblity(self, arc_lyr_to_add, recipe_lyr):
        if arc_lyr_to_add.supports('VISIBLE'):
            try:
                arc_lyr_to_add.visible = recipe_lyr.visible
            except Exception as exp:
                recipe_lyr.error_messages.append('Error whilst applying layer visiblity: {}'.format(
                    exp.message))

    def apply_label_classes(self, arc_lyr_to_add, recipe_lyr):
        if arc_lyr_to_add.supports("LABELCLASSES"):
            for labelClass in recipe_lyr.label_classes:
                for lblClass in arc_lyr_to_add.labelClasses:
                    if (lblClass.className == labelClass.class_name):
                        lblClass.SQLQuery = labelClass.sql_query
                        lblClass.expression = labelClass.expression
                        lblClass.showClassLabels = labelClass.show_class_labels

    def apply_definition_query(self, arc_lyr_to_add, recipe_lyr):
        logging.debug('In method apply_definition_query for layer; {}'.format(recipe_lyr.layer_file_path))
        logging.debug('   Target layer supports DEFINITIONQUERY; {}'.format(arc_lyr_to_add.supports('DEFINITIONQUERY')))
        logging.debug('   Target DEFINITIONQUERY; {}'.format(recipe_lyr.definition_query))
        if recipe_lyr.definition_query and arc_lyr_to_add.supports('DEFINITIONQUERY'):
            try:
                logging.debug('  Attempting to apply definition query')
                arc_lyr_to_add.definitionQuery = recipe_lyr.definition_query
            except Exception as exp:
                logging.error('Error whilst applying definition query: "{}"\n{}'.format(
                    recipe_lyr.definition_query, exp.message))
                recipe_lyr.error_messages.append('Error whilst applying definition query: "{}"\n{}'.format(
                    recipe_lyr.definition_query, exp.message))

    def get_dataset_type_from_path(self, f_path):
        """
        * '.shp' at the end of a path name
        * '.img' at the end of a path name
        * '.tif' at the end of a path name
        * '.gdb\' in the middle of a path name
        """
        dataset_type_lookup = [
            (r'\.shp$', 'SHAPEFILE_WORKSPACE'),
            (r'\.img$', 'RASTER_WORKSPACE'),
            (r'\.tif$', 'RASTER_WORKSPACE'),
            (r'\.gdb\\.+', 'FILEGDB_WORKSPACE')
        ]

        for reg_ex, dataset_type in dataset_type_lookup:
            if re.search(reg_ex, f_path):
                return dataset_type

        raise ValueError('"Unsupported dataset type with path: {}'.format(f_path))

    def addLayerWithFile(self, arc_lyr_to_add, recipe_lyr, recipe_frame):
        # Skip past any layer which didn't already have a source file located   
        print("inside addLayerWithFile")     
        try:
            recipe_lyr.data_source_path
        except AttributeError:
            print(f"Skipping Layer {recipe_lyr.name} which didn't already have a source file located ")
            return
        print("passed to add layer field exist")
        r_path = os.path.realpath(recipe_lyr.data_source_path)
        data_src_dir = os.path.dirname(r_path)
        dataset_type = self.get_dataset_type_from_path(r_path)

        # Apply Data Source
        if arc_lyr_to_add.supports("DATASOURCE"):
            try:
                newConProps = arc_lyr_to_add.connectionProperties
                # print("This is the old  dataset props  -----------------------\n")
                # pprint(newConProps)
                newConProps["dataset"] = recipe_lyr.data_name
                newConProps['connection_info']['database'] = data_src_dir
                #newConProps["workspace_factory"] = dataset_type
                # print("This is the new  dataset props  -----------------------\n")            
                # pprint(newConProps)
                arc_lyr_to_add.updateConnectionProperties(arc_lyr_to_add.connectionProperties,newConProps)
                arc_data_frame = self.aprx.listLayouts("*")[0].listElements("mapframe_element",(recipe_frame.name.replace(" Map Frame", "") + "*"))[0]
                arc_main_map = arc_data_frame.map
                #listMaps((recipe_frame.name.replace(" Map Frame", "") + "*"))[0]
                # TODO add proper fix for applyZoom in line with these two cards
                # https: // trello.com/c/Bs70ru1s/145-design-criteria-for-selecting-zoom-extent
                # https://trello.com/c/piE3tKRp/146-implenment-rules-for-selection-zoom-extent
                # self.applyZoom(self.dataFrame, arc_lyr_to_add, cookBookLayer.get('zoomMultiplier', 0))

                # Is this even required after adding each layer?
                # self.apply_frame_crs_and_extent(arc_data_frame, recipe_frame)

                if recipe_lyr.add_to_legend is False:
                    self.legendEntriesToRemove.append(arc_lyr_to_add.name)
                print(f"adding layer {recipe_lyr.name} via <arcpy-layerfile> to arc_data_frame {recipe_frame.name.replace(' Map Frame', '') + '*'}")
                arc_main_map.addLayer(arc_lyr_to_add, "BOTTOM")
            finally:
                self.aprx.save()

    def zoomToCountry(self):
        # Set map in map-frame:
        lyt = self.aprx.listLayouts("*")[0]
        mainMapFrame = lyt.listElements("mapframe_element", "Main map*")[0]
        mainMap = self.aprx.listMaps("Main map*")[0]
        mainMapFrame.map = mainMap
        mainMapFrame.zoomToAllLayers()
        self.aprx.save()
        for lyr in mainMap.listLayers():
            if (lyr.name == "mainmap-admn-ad1-py-s0-reference"):
                arcpy.SelectLayerByAttribute_management(lyr, "NEW_SELECTION", "1=1")
                layers_exten = mainMapFrame.getLayerExtent(lyr, True, True)
                print("layers extent")
                pprint(layers_exten.JSON)
                mainMapFrame.camera.setExtent(layers_exten)
                mainMapFrame.zoomToAllLayers()
                break