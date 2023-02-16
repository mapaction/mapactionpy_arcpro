import os
import arcpy
# import jsonpickle
# import logging
import re
# import match
import shutil

from mapactionpy_controller.map_cookbook import MapCookbook
# from mapactionpy_controller.recipe_layer import RecipeLayer
from mapactionpy_controller.layer_properties import LayerProperties
# from mapactionpy_controller.map_report import MapReport
# from mapactionpy_controller.map_result import MapResult
# from mapactionpy_controller.data_source import DataSource
from datetime import datetime

# TODO asmith 2020/03/06
# What is the separation of responsiblities between MapChef and ArcProRunner? Why is the boundary
# between the two classes where it is? If I was to add a new function how would I know whether it
# should be added to MapChef or ArcProRunner?
#
# Is it intended that the `cook()` method might be called multiple times in the life of a MapChef
# object? At present it looks to me like `cook()` can only be called once. In which case why have
# `cook()` as a public method and why not call it directly from the constructor.


class MapChef:
    """
    Worker which creates a Map based on a predefined "recipe" from a cookbook
    """
    def __init__(self,
                 runner):
        self.layerSubFolders = ["3121_arcpro", "3121_arcpro\\mapchef-versions"]
        self.templateSubFolder = "321_arcpro"
        self.runner = runner
        now = datetime.now()
        
        self.createTime = now.strftime("%H:%M:%S")
        self.createDate = now.strftime("%d/%m/%Y")

        print (self.runner.cmf.map_definitions)
        self.crashMoveFolder = self.runner.cmf
        self.eventConfiguration = self.runner.hum_event
        self.cookbook = MapCookbook(self.runner.cmf.map_definitions)
        self.layerProperties = LayerProperties(self.runner.cmf)
        self.activeDataFilesDict = {}

    def setRecipe(self, mapnumber):
        if (mapnumber in self.cookbook.products):
            self.recipe = self.cookbook.products[mapnumber]
        else:
            raise ValueError('Could not find recipe with number ' + mapnumber + " in cookbook.")

    def cook(self,
             mapnumber,
             overwrite):
        # Do we have the map number in the cook book?
        print ("Cook: " + mapnumber)

        self.setRecipe(mapnumber)
        print("After setRecipe")
        self.setActiveDataFiles()
        destinationAprx = self.createNewProjectFile(mapnumber, overwrite)
        print(destinationAprx)

        if (destinationAprx):
        # Open APRX, List Layouts
            print ("Opening: " + destinationAprx)
            self.aprx = arcpy.mp.ArcGISProject(destinationAprx)
            self.addLayers()
            self.updateTextElements()
            self.addDataSources()
            self.zoomToCountry()

    def createNewProjectFile(self, mapnumber, overwrite = False):
        destinationAprx = None
        projectFolder = os.path.join(self.crashMoveFolder.map_projects, (mapnumber + "_" + (self.recipe.product.replace(" ", "_"))))
        if os.path.exists(projectFolder):
            if (overwrite == False):
                raise ValueError(
                    'Folder {} already exists.  '
                    'Use --overwrite.'.format(projectFolder))
                return
        else:
            os.mkdir(projectFolder)
        # Copy .aprx to Project Folder.
        srcAprx = os.path.join(self.crashMoveFolder.map_templates, self.templateSubFolder, "pro_2.8_all_templates.aprx")
        destinationAprx = os.path.join(projectFolder, mapnumber +"-v01-" + (self.eventConfiguration.affected_country_iso3).lower() + "_" + ((self.recipe.product.replace(" ", "-")).lower())+".aprx")
        shutil.copyfile(srcAprx, destinationAprx)
        return destinationAprx

    def addLayers(self):
        # For each map in the recipe
        for mapFromRecipe in self.recipe.map_frames:
            mapframeFromAprx = self.aprx.listMaps(mapFromRecipe.name)[0]
            for layerFromRecipe in mapFromRecipe.layers:
                foundLayerFile = False
                for subFolder in self.layerSubFolders:
                    lyrx = os.path.join(self.crashMoveFolder.layer_rendering, subFolder, layerFromRecipe.name + ".lyrx")
                    # If this path to the .lyrx file exists, add it to the map.
                    if foundLayerFile == False:
                        if os.path.exists(lyrx):
                            print ("Adding: " + lyrx)
                            layerToAdd = arcpy.mp.LayerFile(lyrx)
                            mapframeFromAprx.addLayer(layerToAdd)
                            self.aprx.save()
                            foundLayerFile = True

    def addDataSources(self):
        print ("addDataSources")
        for mapFromRecipe in self.recipe.map_frames:
            mapframeFromAprx = self.aprx.listMaps(mapFromRecipe.name)[0]
            for layerFromRecipe in mapFromRecipe.layers:
                lyr = mapframeFromAprx.listLayers(layerFromRecipe.name)[0]
                layerProperties = self.layerProperties.properties[layerFromRecipe.name]

                regexp = layerProperties.reg_exp.replace("{e.affected_country_iso3}", self.eventConfiguration.affected_country_iso3)
                # if (len(layerProperties.definition_query) > 0):
                #     definitionQuery = layerProperties.definition_query.replace("{e.country_name}", self.eventConfiguration.country_name)
                #     lyr.definition_query = definitionQuery
                #     print ("DEFINITION QUERY : " + definitionQuery)
                #     self.aprx.save()
                #     # arcpy.SelectLayerByAttribute_management(lyr, "SUBSET_SELECTION", definitionQuery)

                for key in self.activeDataFilesDict:
                    if re.match(regexp, key):
                        fullPath = self.activeDataFilesDict[key]
                        print ("ADDING : " + lyr.name + " / " + fullPath)
                        path = os.path.dirname(fullPath)
                        fileName = os.path.basename(fullPath)
                        cp = lyr.connectionProperties
                        cp['connection_info']['database'] = path
                        cp['dataset'] = fileName

                        lyr.updateConnectionProperties(lyr.connectionProperties, cp)
                        self.aprx.save()
                        break
            
    def setActiveDataFiles(self):
        for folder, subfolders, files in os.walk(self.crashMoveFolder.active_data):
            for file in files:
                filePath = os.path.abspath(os.path.join(folder, file))
                self.activeDataFilesDict[file]=filePath

    def updateTextElements(self):
        for mapFromRecipe in self.recipe.map_frames:
            mapframeFromAprx = self.aprx.listMaps(mapFromRecipe.name)[0]
            print ("Got map: " + mapframeFromAprx.name)
            for lyt in self.aprx.listLayouts("*"):
                for elm in lyt.listElements("TEXT_ELEMENT", "*"):
                    if elm.name == "country":
                        elm.text = self.eventConfiguration.operation_name
                    if elm.name == "title":
                        elm.text = self.recipe.product
                    if elm.name == "create_date_time":
                        elm.text = self.createDate + " " + self.createTime
                    if elm.name == "summary":
                        elm.text = self.recipe.summary
                    if elm.name == "map_no":
                        # versionNumberString = "v" + str(self.recipe.version_num).zfill(2)
                        elm.text = self.recipe.mapnumber
                        # + " " + versionNumberString
                    if elm.name == "mxd_name":
                        elm.text = os.path.basename(self.aprx.filePath)
                    if elm.name == "scale":
                        elm.text = self.scale()
                    # if elm.name == "data_sources":
                    #     iter = 0
                    #     dataSourcesString = "<BOL>Data Sources:</BOL>" + os.linesep + os.linesep
                    #     for ds in self.dataSources:
                    #         if (iter > 0):
                    #             dataSourcesString = dataSourcesString + ", "
                    #         dataSourcesString = dataSourcesString + ds
                    #         iter = iter + 1
                    #     elm.text = dataSourcesString
                    # if elm.name == "spatial_reference":
                    #     elm.text = self.spatialReference()
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


    # def disableLayers(self):
    #     """
    #     Makes all layers invisible for all data-frames
    #     """
    #     for m in self.aprx.listMaps("*"):
    #         for lyr in m.listLayers():
    #             lyr.visible = False

    # def returnScale(self, dfscale):
    #     # https://community.esri.com/thread/163596
    #     scalebar = [2, 3, 4, 5, 6, 10]
    #     dfscale = dfscale/12
    #     dfscale = str(int(dfscale))
    #     dfscaleLen = len(dfscale)
    #     numcheck = int(dfscale[0])
    #     for each in scalebar:
    #         if numcheck < each:
    #             multi = '1'
    #             while dfscaleLen > 1:
    #                 multi = multi + '0'
    #                 dfscaleLen = dfscaleLen - 1
    #             scalebar = each * int(multi)
    #             dataframescale = scalebar * 12
    #             return scalebar, dataframescale

    def scale(self):
        newScale = ""
        lyt = self.aprx.listLayouts("*")[0]

        for df in lyt.listElements("MAPFRAME_ELEMENT", "Main map*"):
            intValue = '{:,}'.format(int(df.camera.scale))
            newScale = "1: " + intValue + " (At A3)"
            break

        return newScale

    # def spatialReference(self):
    #     spatialReferenceString = "Unknown"
    #     lyt = self.aprx.listLayouts("*")[0]

    #     for df in lyt.listElements("MAPFRAME_ELEMENT", "Main map*"):
    #         if (len(df.spatialReference.datumName) > 0):
    #             spatialReferenceString = df.spatialReference.datumName
    #             spatialReferenceString = spatialReferenceString[2:]
    #             spatialReferenceString = spatialReferenceString.replace('_', ' ')
    #         break
    #     return spatialReferenceString

    # # TODO asmith 2020/0306
    # # Do we need to accommodate a use case where we would want to add layers but not make them
    # # visible? If so is this something that we deal with when we get to it?
    # def enableLayers(self):
    #     """
    #     Makes all layers visible for all data-frames
    #     """
    #     for m in self.aprx.listMaps("*"):
    #         for lyr in m.listLayers():
    #             lyr.visible = True

    # def removeLayers(self):
    #     """
    #     Removes all layers for all data-frames
    #     """

    #     for m in self.aprx.listMaps("*"):
    #         for lyr in m.listLayers():
    #             if (lyr.longName != "Data Driven Pages"):
    #                 arcpy.mp.RemoveLayer(lyr)

    #     self.aprx.save()

    # # TODO asmith 2020/03/06

    # def cook(self, recipe, replaceDataSourceOnly=False):
    #     self.recipe = recipe
    #     self.replaceDataSourceOnly = replaceDataSourceOnly
    #     arcpy.env.addOutputsToMap = False
    #     if not replaceDataSourceOnly:
    #         self.disableLayers()
    #         self.removeLayers()

    #     self.mapReport = MapReport(self.recipe.product)
    #     if (self.recipe is not None):
    #         if len(self.recipe.summary):
    #             self.summary = self.recipe.summary
    #         for mf in self.recipe.map_frames:
    #             for layer in mf.layers:
    #                 print(layer.name + "/" + mf.name)
    #                 self.process_layer(layer, mf)

    #     self.zoomToCountry()

    #     self.enableLayers()
    #     arcpy.env.addOutputsToMap = True
    #     self.aprx.save()

    #     if (recipe is not None):
    #         self.updateTextElements()
    #         self.aprx.save()

    # """
    # Adds data file to map layer

    # Can handle the following file types:
    #     * Shapefiles
    #     * IMG files
    #     * TIF files

    # Arguments:
    #     dataFrame {str} -- Name of data frame to add data source file to
    #     dataFile {str}  -- Full path to data file
    #     layer {arcpy._mapping.Layer} -- Layer to which data is added
    #     definitionQuery {str} -- Some layers have a definition query which select specific features from a SQL query
    #     labelClasses {list} -- List of LabelClass objects

    # Returns:
    #     boolean -- added (true if successful)
    # """

    # def addDataToLayer(self,
    #                    dataFrame,
    #                    dataFile,
    #                    layer,
    #                    definitionQuery,
    #                    datasetName,
    #                    labelClasses,
    #                    addToLegend,
    #                    zoomMultiplier=0):
    #     added = False
    #     for lyr in arcpy.mapping.ListLayers(layer):
    #         if lyr.supports("LABELCLASSES"):
    #             for labelClass in labelClasses:
    #                 for lblClass in lyr.label_classes:
    #                     if (lblClass.className == labelClass.className):
    #                         lblClass.SQLQuery = labelClass.sql_query.replace('{COUNTRY_NAME}',
    #                                                                          self.eventConfiguration.country_name)
    #                         lblClass.expression = labelClass.expression
    #                         lblClass.showClassLabels = labelClass.show_class_labels
    #         if lyr.supports("DATASOURCE"):  # An annotation layer does not support DATASOURCE
    #             for datasetType in self.datasetTypes:
    #                 try:
    #                     lyr.replaceDataSource(dataFile, datasetType, datasetName)
    #                     added = True
    #                 except Exception:
    #                     pass

    #                 if ((added is True) and (definitionQuery)):
    #                     definitionQuery = definitionQuery.replace('{COUNTRY_NAME}',
    #                                                               self.eventConfiguration.country_name)
    #                     lyr.definition_query = definitionQuery
    #                     try:
    #                         arcpy.SelectLayerByAttribute_management(lyr, "SUBSET_SELECTION", definitionQuery)
    #                     except Exception:
    #                         added = False

    #                 if (added is True):
    #                     if addToLegend is False:
    #                         self.legendEntriesToRemove.append(lyr.name)
    #                         if (self.namingConvention is not None):
    #                             dnr = self.namingConvention.validate(datasetName)
    #                             # We want to capture Description:
    #                             if 'Description' in dnr.source._fields:
    #                                 if (dnr.source.Description.lower() not in ('unknown', 'undefined', 'mapaction')):
    #                                     self.dataSources.add(dnr.source.Description)

    #                     if (self.replaceDataSourceOnly):
    #                         self.aprx.save()
    #                     else:
    #                         arcpy.mapping.AddLayer(dataFrame, lyr, "BOTTOM")
    #                     break
    #             lyr.visible = False
    #             self.applyZoom(dataFrame, lyr, zoomMultiplier)

    #     return added

    # def report_as_json(self):
    #     """
    #     Returns map report in json format
    #     """
    #     return(jsonpickle.encode(self.mapReport, unpicklable=False))

    # def process_layer(self, recipe_lyr, recipe_frame):
    #     """
    #     Updates or Adds a layer of data.  Maintains the Map Report.
    #     """
    #     mapResult = MapResult(recipe_lyr.name)
    #     lyt = self.aprx.listLayouts("*")[0]
    #     arc_data_frame = lyt.listElements("MAPFRAME_ELEMENT", (recipe_frame.name + "*"))[0]

    #     try:
    #         # BUG
    #         # The layer name in the TOC is not necessarily == recipe_lyr.name
    #         # arc_lyr_to_update = arcpy.mapping.ListLayers(self.aprx, recipe_lyr.name, self.dataFrame)[0]
    #         # Try this instead
    #         # lyr_index = recipe_frame.layers.index(recipe_lyr)

    #         # arc_lyr_to_update = None
    #         # for m in self.aprx.listMaps("*"):
    #         #    for lyr in m.listLayers():
    #         #        print(lyr.name)
    #         #        if (lyr.name == recipe_lyr.name):
    #         #            arc_lyr_to_update = lyr

    #         # arc_lyr_to_update = arcpy.mapping.ListLayers(self.aprx, None, arc_data_frame)[lyr_index]

    #         mapResult = self.addLayer(recipe_lyr, arc_data_frame)
    #         # Replace existing layer
    #         # mapResult = self.updateLayer(arc_lyr_to_update, recipe_lyr, recipe_frame)
    #     except IndexError:
    #         # Layer doesn't exist, add new layer
    #         mapResult = self.addLayer(recipe_lyr, arc_data_frame)

    #     self.mapReport.add(mapResult)

    # def find(self, rootdir, regexp, gdb=False):
    #     returnPaths = list()
    #     # TODO asmith 2020/03/06
    #     # What is the purpose of wrangling the regexps here?
    #     # The regexs in the layerProperties.json just match the filenames. The purpose of this
    #     # seems to be to change the regexs to work on the full path, and then later join the full
    #     # filename with the directory path before attempting to match the regexs.
    #     # I suspect there are some edge cases where incorrectly named files could inadvertantly
    #     # matched here.
    #     regexp = regexp.replace("^", "\\\\")
    #     regexp = regexp.replace("/", "\\\\")
    #     regexp = ".*" + regexp
    #     re.compile(regexp)
    #     for root, dirs, files in os.walk(os.path.abspath(rootdir)):
    #         if (gdb is False):
    #             for file in files:
    #                 filePath = os.path.join(root, file)
    #                 z = re.match(regexp, filePath)
    #                 if (z):
    #                     # TODO asmith 2020/03/06
    #                     # Is this necessary? Having a `$` at the end of the regex would have the
    #                     # effect of as excluding the lock files.
    #                     if not(filePath.endswith("lock")):
    #                         returnPaths.append(filePath)
    #         else:
    #             for dir in dirs:
    #                 dirPath = os.path.join(root, dir)
    #                 z = re.match(regexp, dirPath)
    #                 if (z):
    #                     returnPaths.append(dirPath)
    #     return returnPaths

    # """
    # Updates Text Elements in Marginalia

    # """

    # def updateTextElements(self):
    #     lyt = self. aprx.listLayouts()[0]

    #     for elm in lyt.listElements("TEXT_ELEMENT"):
    #         if elm.name == "country":
    #             elm.text = self.eventConfiguration.country_name
    #         if elm.name == "title":
    #             elm.text = self.recipe.product
    #         if elm.name == "create_date_time":
    #             elm.text = self.createDate + " " + self.createTime
    #         if elm.name == "summary":
    #             elm.text = self.summary
    #         if elm.name == "map_no":
    #             versionNumberString = "v" + str(self.recipe.version_num).zfill(2)
    #             elm.text = self.recipe.mapnumber + " " + versionNumberString
    #         if elm.name == "mxd_name":
    #             elm.text = os.path.basename(self.aprx.filePath)
    #         if elm.name == "scale":
    #             elm.text = self.scale()
    #         if elm.name == "data_sources":
    #             iter = 0
    #             dataSourcesString = "<BOL>Data Sources:</BOL>" + os.linesep + os.linesep
    #             for ds in self.dataSources:
    #                 if (iter > 0):
    #                     dataSourcesString = dataSourcesString + ", "
    #                 dataSourcesString = dataSourcesString + ds
    #                 iter = iter + 1
    #             elm.text = dataSourcesString
    #         if elm.name == "spatial_reference":
    #             elm.text = self.spatialReference()
    #         if elm.name == "glide_no":
    #             if self.eventConfiguration and self.eventConfiguration.glide_number:
    #                 elm.text = self.eventConfiguration.glide_number
    #         if elm.name == "donor_credit":
    #             if (self.eventConfiguration is not None):
    #                 elm.text = self.eventConfiguration.default_donor_credits
    #         if elm.name == "disclaimer":
    #             if (self.eventConfiguration is not None):
    #                 elm.text = self.eventConfiguration.default_disclaimer_text
    #         if elm.name == "map_producer":
    #             if (self.eventConfiguration is not None):
    #                 elm.text = "Produced by " + \
    #                     self.eventConfiguration.default_source_organisation + \
    #                     os.linesep + \
    #                     self.eventConfiguration.deployment_primary_email + \
    #                     os.linesep + \
    #                     self.eventConfiguration.default_source_organisation_url
    #     self.aprx.save()

    # def showLegendEntries(self):
    #     for legend in arcpy.mapping.ListLayoutElements(self.aprx, "LEGEND_ELEMENT"):
    #         layerNames = list()
    #         for lyr in legend.listLegendItemLayers():
    #             if ((lyr.name in self.legendEntriesToRemove) or (lyr.name in layerNames)):
    #                 legend.removeItem(lyr)
    #             else:
    #                 layerNames.append(lyr.name)
    #     self.aprx.save()

    # # TODO asmith 2020/03/06
    # # Please don't hard code size and location of elements on the template
    # def alignLegend(self, orientation):
    #     for legend in arcpy.mapping.ListLayoutElements(self.aprx, "LEGEND_ELEMENT"):
    #         if orientation == "landscape":
    #             # Resize
    #             legend.elementWidth = 60
    #             legend.elementPositionX = 248.9111
    #             legend.elementPositionY = 40
    #     self.aprx.save()

    # # TODO asmith 2020/03/06
    # # Please don't hard code size and location of elements on the template
    # def resizeScaleBar(self):
    #     elm = arcpy.mapping.ListLayoutElements(self.aprx, "MAPSURROUND_ELEMENT", "Scale Bar")[0]
    #     elm.elementWidth = 51.1585
    #     self.aprx.save()

    # def applyZoom(self, dataFrame, lyr, zoomMultiplier):
    #     if (zoomMultiplier != 0):
    #         buffer = zoomMultiplier
    #         arcpy.env.overwriteOutput = "True"
    #         extent = lyr.getExtent(True)  # visible extent of layer

    #         extBuffDist = ((int(abs(extent.lowerLeft.X - extent.lowerRight.X))) * buffer)

    #         # TODO asmith 2020/03/06
    #         # This is untested but possibly much terser:
    #         # ```
    #         #        x_min = extent.XMin - extBuffDist
    #         #        y_min = extent.YMin - extBuffDist
    #         #        x_max = extent.XMax + extBuffDist
    #         #        y_max = extent.YMax + extBuffDist
    #         #        new_extent = arcpy.Extent(x_min, y_min, x_max, y_max)
    #         #        dataFrame.extent = new_extent
    #         # ```

    #         newExtentPts = arcpy.Array()
    #         newExtentPts.add(arcpy.Point(extent.lowerLeft.X-extBuffDist,
    #                                      extent.lowerLeft.Y-extBuffDist,
    #                                      extent.lowerLeft.Z,
    #                                      extent.lowerLeft.M,
    #                                      extent.lowerLeft.ID))

    #         newExtentPts.add(arcpy.Point(extent.lowerRight.X+extBuffDist,
    #                                      extent.lowerRight.Y-extBuffDist,
    #                                      extent.lowerRight.Z,
    #                                      extent.lowerRight.M,
    #                                      extent.lowerRight.ID))

    #         newExtentPts.add(arcpy.Point(extent.upperRight.X+extBuffDist,
    #                                      extent.upperRight.Y+extBuffDist,
    #                                      extent.upperRight.Z,
    #                                      extent.upperRight.M,
    #                                      extent.upperRight.ID))

    #         newExtentPts.add(arcpy.Point(extent.upperLeft.X-extBuffDist,
    #                                      extent.upperLeft.Y+extBuffDist,
    #                                      extent.upperLeft.Z,
    #                                      extent.upperLeft.M,
    #                                      extent.upperLeft.ID))

    #         newExtentPts.add(arcpy.Point(extent.lowerLeft.X-extBuffDist,
    #                                      extent.lowerLeft.Y-extBuffDist,
    #                                      extent.lowerLeft.Z,
    #                                      extent.lowerLeft.M,
    #                                      extent.lowerLeft.ID))
    #         polygonTmp2 = arcpy.Polygon(newExtentPts)
    #         dataFrame.extent = polygonTmp2
    #         self.aprx.save()

    # # TODO: asmith 2020/03/06
    # # `updateLayer()` and `addLayer()` seem very similar. Is it possible to refactor to reduce
    # # duplication?
    # def updateLayer(self, arc_lyr_to_update, recipe_lyr, recipe_frame):
    #     mapResult = None

    #     if (".gdb/" not in recipe_lyr.reg_exp):
    #         mapResult = self.updateLayerWithFile(recipe_lyr, arc_lyr_to_update,
    #                                              recipe_lyr.layer_file_path, recipe_frame)
    #     else:
    #         mapResult = self.updateLayerWithGdb(recipe_lyr, recipe_frame)
    #     return mapResult

    # # TODO: asmith 2020/03/06
    # # `updateLayer()` and `addLayer()` seem very similar. Is it possible to refactor to reduce
    # # duplication?
    # def addLayer(self, recipe_lyr, recipe_frame):
    #     mapResult = MapResult(recipe_lyr.name)
    #     logging.debug('Attempting to add layer; {}'.format(recipe_lyr.layer_file_path))
    #     lyrFile = arcpy.mp.LayerFile(recipe_lyr.layer_file_path)

    #     for arc_lyr_to_add in lyrFile.listLayers():
    #         if (".gdb/" not in recipe_lyr.reg_exp):
    #             mapResult = self.addLayerWithFile(recipe_lyr, arc_lyr_to_add, recipe_lyr.name, recipe_frame)
    #         else:
    #             mapResult = self.addLayerWithGdb(recipe_lyr, arc_lyr_to_add, recipe_lyr.name, recipe_frame)
    #     return mapResult

    # # TODO: asmith 2020/03/06
    # # These three methods appear very similar:
    # #   * `addLayerWithFile()`
    # #   * `addLayerWithGdb()`
    # #   * `updateLayerWithFile()`
    # # Is it possible to refactor to reduce duplication?
    # def updateLayerWithFile(self, layerProperties, updateLayer, layerFilePath, recipe_frame):
    #     mapResult = MapResult(layerProperties.name)

    #     dataFiles = self.find(self.crashMoveFolder.active_data, layerProperties.reg_exp)
    #     for dataFile in (dataFiles):
    #         base = os.path.basename(dataFile)
    #         datasetName = os.path.splitext(base)[0]
    #         dataDirectory = os.path.dirname(os.path.realpath(dataFile))

    #         sourceLayer = arcpy.mapping.Layer(layerFilePath)
    #         arc_data_frame = arcpy.mapping.ListDataFrames(self.aprx, recipe_frame.name)[0]
    #         arcpy.mapping.UpdateLayer(arc_data_frame, updateLayer, sourceLayer, False)

    #         # BUG
    #         # The layer name in the TOC is not necessarily == recipe_lyr.name
    #         # newLayer = arcpy.mapping.ListLayers(self.aprx, updateLayer.name, self.dataFrame)[0]
    #         # Try this instead
    #         lyr_index = recipe_frame.layers.index(updateLayer)
    #         newLayer = arcpy.mapping.ListLayers(self.aprx, None, arc_data_frame)[lyr_index]

    #         if newLayer.supports("DATASOURCE"):
    #             for datasetType in self.datasetTypes:
    #                 try:
    #                     if (newLayer.supports("DEFINITIONQUERY") and (layerProperties.definition_query)):
    #                         newLayer.definition_query = layerProperties.definition_query.replace(
    #                             '{COUNTRY_NAME}', self.eventConfiguration.country_name)
    #                     newLayer.replaceDataSource(dataDirectory, datasetType, datasetName)
    #                     mapResult.message = "Layer updated successfully"
    #                     mapResult.added = True
    #                     ds = DataSource(dataFile)
    #                     mapResult.dataSource = dataFile.replace("\\", "/").replace(self.crashMoveFolder.path.replace("\\", "/"), "")   # noqa
    #                     mapResult.hash = ds.calculate_checksum()
    #                     break
    #                 except Exception:
    #                     pass

    #         if (mapResult.added is True):
    #             self.aprx.save()
    #             break
    #     return mapResult

    # def updateLayerWithGdb(self, layerProperties, recipe_frame):
    #     mapResult = MapResult(layerProperties.name)
    #     mapResult.message = "Update layer for a GeoDatabase not yet implemented"
    #     return mapResult

    # # TODO: asmith 2020/03/06
    # # These three methods appear very similar:
    # #   * `addLayerWithFile()`
    # #   * `addLayerWithGdb()`
    # #   * `updateLayerWithFile()`
    # # Is it possible to refactor to reduce duplication?
    # def addLayerWithFile(self, layerProperties, layerToAdd, cookBookLayer, recipe_frame):
    #     mapResult = MapResult(layerProperties.name)
    #     dataFiles = self.find(self.crashMoveFolder.active_data, layerProperties.reg_exp)

    #     for dataFile in (dataFiles):
    #         base = os.path.basename(dataFile)
    #         datasetName = os.path.splitext(base)[0]
    #         dataDirectory = os.path.dirname(os.path.realpath(dataFile))

    #         if layerToAdd.supports("labelclasses"):
    #             for labelClass in layerProperties.label_classes:
    #                 for lblClass in layerToAdd.labelClasses:
    #                     if (lblClass.className == labelClass.class_name):
    #                         lblClass.SQLQuery = labelClass.sql_query.replace('{COUNTRY_NAME}',
    #                                                                          self.eventConfiguration.country_name)
    #                         lblClass.expression = labelClass.expression
    #                         lblClass.showClassLabels = labelClass.show_class_labels

    #         if layerToAdd.supports("datasource"):
    #             for datasetType in self.datasetTypes:
    #                 try:
    #                     cp = layerToAdd.connectionProperties

    #                     cp['connection_info']['database'] = dataDirectory
    #                     cp['dataset'] = datasetName + ".shp"  # Use dictionary for suffixes
    #                     layerToAdd.updateConnectionProperties(layerToAdd.connectionProperties, cp)

    #                     # layerToAdd.replaceDataSource(dataDirectory, datasetType, datasetName)
    #                     mapResult.message = "Layer added successfully"
    #                     mapResult.added = True
    #                     ds = DataSource(dataFile)
    #                     mapResult.dataSource = dataFile.replace("\\", "/").replace(self.crashMoveFolder.path.replace("\\", "/"), "")   # noqa
    #                     mapResult.hash = ds.calculate_checksum()
    #                     break
    #                 except Exception:
    #                     pass

    #         if ((mapResult.added is True) and (layerProperties.definition_query)):
    #             definitionQuery = layerProperties.definition_query.replace('{COUNTRY_NAME}',
    #                                                                         self.eventConfiguration.country_name)  # NOQA
    #             layerToAdd.definition_query = definitionQuery
    #             try:
    #                 arcpy.SelectLayerByAttribute_management(layerToAdd,
    #                                                         "SUBSET_SELECTION",
    #                                                         layerProperties.definition_query)
    #             except Exception:
    #                 mapResult.added = False
    #                 mapResult.message = "Selection query failed: " + layerProperties.definition_query
    #                 self.aprx.save()

    #         if (mapResult.added is True):
    #             # TODO add proper fix for applyZoom in line with these two cards
    #             # https: // trello.com/c/Bs70ru1s/145-design-criteria-for-selecting-zoom-extent
    #             # https://trello.com/c/piE3tKRp/146-implenment-rules-for-selection-zoom-extent
    #             # self.applyZoom(self.dataFrame, layerToAdd, cookBookLayer.get('zoomMultiplier', 0))
    #             # SAH self.applyZoom(arc_data_frame, layerToAdd, 0)

    #             m = self.aprx.listMaps((recipe_frame.name.replace(" Map Frame", "") + "*"))
    #             m[0].addLayer(layerToAdd, "BOTTOM")
    #             self.aprx.save()
    #             break

    #     return mapResult

    # # TODO: asmith 2020/03/06
    # # These three methods appear very similar:
    # #   * `addLayerWithFile()`
    # #   * `addLayerWithGdb()`
    # #   * `updateLayerWithFile()`
    # # Is it possible to refactor to reduce duplication?
    # def addLayerWithGdb(self, layerProperties, layerToAdd, cookBookLayer, recipe_frame):
    #     mapResult = MapResult(layerProperties.name)

    #     # It's a File Geodatabase
    #     parts = layerProperties.reg_exp.split("/")
    #     gdbPath = parts[0]
    #     geoDatabases = self.find(self.crashMoveFolder.active_data, gdbPath, True)
    #     for geoDatabase in geoDatabases:
    #         arcpy.env.workspace = geoDatabase
    #         rasters = arcpy.ListRasters("*")
    #         for raster in rasters:
    #             if re.match(parts[1], raster):
    #                 arc_data_frame = arcpy.mapping.ListDataFrames(self.aprx, recipe_frame.name)[0]
    #                 mapResult.added = self.addDataToLayer(arc_data_frame,
    #                                                       geoDatabase,
    #                                                       layerToAdd,
    #                                                       layerProperties.definition_query,
    #                                                       raster,
    #                                                       layerProperties.label_classes,
    #                                                       layerProperties.add_to_legend)

    #                 dataFile = geoDatabase + os.sep + raster
    #                 ds = DataSource(dataFile)
    #                 mapResult.dataSource = dataFile.replace("\\", "/").replace(self.crashMoveFolder.path.replace("\\", "/"), "")  # noqa
    #                 mapResult.hash = ds.calculate_checksum()
    #                 break
    #         featureClasses = arcpy.ListFeatureClasses()
    #         for featureClass in featureClasses:
    #             if re.match(parts[1], featureClass):
    #                 # Found Geodatabase.  Stop iterating.
    #                 arc_data_frame = arcpy.mapping.ListDataFrames(self.aprx, recipe_frame.name)[0]
    #                 mapResult.added = self.addDataToLayer(arc_data_frame,
    #                                                       geoDatabase,
    #                                                       layerToAdd,
    #                                                       layerProperties.definition_query,
    #                                                       featureClass,
    #                                                       layerProperties.label_classes,
    #                                                       layerProperties.add_to_legend)
    #                 dataFile = geoDatabase + os.sep + featureClass
    #                 ds = DataSource(dataFile)
    #                 mapResult.dataSource = dataFile.replace("\\", "/").replace(self.crashMoveFolder.path.replace("\\", "/"), "")  # noqa
    #                 mapResult.hash = ds.calculate_checksum()
    #                 break

    #     return mapResult

    def zoomToCountry(self):
        # Set map in map-frame:
        lyt = self.aprx.listLayouts("*")[0]
        mainMapFrame = lyt.listElements("mapframe_element", "Main map*")[0]
        mainMap = self.aprx.listMaps("Main map*")[0]
        print ("zoomToCountry() : " + mainMap.name)
        mainMapFrame.map = mainMap
        mainMapFrame.zoomToAllLayers()
        self.aprx.save()
        for lyr in mainMap.listLayers():
            if (lyr.name == "mainmap-admn-ad1-py-s0-reference"):
                print ("zoomToCountry() : Layer - " + lyr.name)
                arcpy.MakeFeatureLayer_management(clipping_layer, 'clippingLayer')
                arcpy.SelectLayerByAttribute_management(lyr, "NEW_SELECTION", "1=1")
                mainMapFrame.camera.setExtent(mainMapFrame.getLayerExtent(lyr, True, True))
                mainMapFrame.panToExtent (mainMapFrame.getLayerExtent(lyr, True, True))
                mainMapFrame.zoomToAllLayers()
                # mainMapFrame.RefreshActiveView()
                mainMapFrame.camera.setExtent(mainMapFrame.getLayerExtent(lyr, False, True))
                mainMap.defaultCamera = mainMapFrame.camera

                # mainMapFrame.zoomToSelectedFeatures()
                # arcpy.RefreshActiveView()
                self.aprx.save()
                break
