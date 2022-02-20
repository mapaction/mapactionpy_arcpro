import arcpy
import logging
import os
from shutil import copyfile
from PIL import Image
from resizeimage import resizeimage
from slugify import slugify
from mapactionpy_arcpro.map_chef import MapChef
from mapactionpy_controller.plugin_base import BaseRunnerPlugin
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(module)s %(name)s.%(funcName)s +%(lineno)s: %(levelname)-8s %(message)s'
)

logger = logging.getLogger(__name__)


class ArcProRunner(BaseRunnerPlugin):
    """
    ArcProRunner - Executes the ArcPro automation methods
    """

    def __init__(self,
                 hum_event,
                 useCurrent=False):
        super(ArcProRunner, self).__init__(hum_event)

        self.exportMap = False
        self.useCurrent = useCurrent
        self.minx = 0
        self.miny = 0
        self.maxx = 0
        self.maxy = 0
        self.chef = None

    def build_project_files(self, **kwargs):
        # Construct a Crash Move Folder object if the cmf_description.json exists
        recipe = kwargs['state']

        aprx = arcpy.mp.ArcGISProject(recipe.map_project_path)

        self.chef = MapChef(aprx, self.cmf, self.hum_event)
        self.chef.cook(recipe)
        # self.chef.alignLegend(self.hum_event.orientation)

        # Output the Map Generation report alongside the MXD
        reportJsonFile = recipe.map_project_path.replace(".aprx", ".json")
        with open(reportJsonFile, 'w') as outfile:
            outfile.write(self.chef.report_as_json())

        return recipe

    def get_projectfile_extension(self):
        return '.pagx'

    def get_project_file_extension(self):
        return '.aprx'

    def get_lyr_render_extension(self):
        return '.lyr'

    def get_text_elements(self, layout):
        # https://pro.arcgis.com/en/pro-app/arcpy/mapping/textelement-class.htm
        text_element_dict = {}
        for elm in layout.listElements("TEXT_ELEMENT", "*"):
            text_element_dict[elm.name] = elm.text
        return text_element_dict

    def _get_largest_map_frame(self, data_frames):
        """
        This returns the dataframe occupying the largest area on the page.
        * If two data frames have identical areas then the widest is returned.
        * If two data frames have identical heights and widths returned then the alphabetically last (by `.name`)
          is returned.

        @param data_frames: a list of DataFrame objects, typically returned by `arcpy.mapping.ListDataFrames(mxd, "*")`
        @return: a single DataFrame object from the list.
        @raises ValueError: if there are two DataFrames in the list, which have identical `width`, `height` and `name`.
        """
        # df, area, width, name
        full_details = [{
            'df': df,
            'area': df.elementHeight*df.elementWidth,
            'width': df.elementWidth,
            'name': df.name} for df in data_frames]

        # select just the largest if there is a single largest
        # keep drilling down using different metrics until a single aspect ratio is discovered
        for metric_key in ['area', 'width', 'name']:
            max_size = max([df_detail[metric_key] for df_detail in full_details])
            sub_list = [df_detail for df_detail in full_details if df_detail[metric_key] == max_size]
            if len(sub_list) == 1:
                return sub_list[0]['df']

            # reduce the list of possible data frames for the next iteration
            full_details = sub_list

        # This means that there are two or more data frames with the same name and this is an error condition
        raise ValueError('There are two or more data frames with the same name')

    def get_aspect_ratio_of_target_area(self, recipe):
        pass

    def get_aspect_ratios_of_templates(self, possible_templates):
        """
        Calculates the aspect ratio of the largest* map frame within the list of templates.

        @param possible_templates: A list of paths to possible templates
        @returns: A list of tuples. For each tuple the first element is the path to the template. The second
                  element is the aspect ratio of the largest* map frame within that template.
                  See `_get_largest_map_frame` for the description of hour largest is determined.
        """
        logging.debug('Calculating the aspect ratio of the largest map frame within the list of templates.')
        results = []

        aprxPath = os.path.join(self.cmf.map_templates, 'pro-2.5-blank-project.aprx')
        aprx = arcpy.mp.ArcGISProject(aprxPath)

        layoutIndex = 0
        for template in possible_templates:
            aprx.importDocument(template)

            lyt = aprx.listLayouts()[layoutIndex]
            map_frame = self._get_largest_map_frame(lyt.listElements("MAPFRAME_ELEMENT", "*"))

            aspect_ratio = float(map_frame.elementWidth)/map_frame.elementHeight
            results.append((template, aspect_ratio))
            logging.debug('Calculated aspect ratio= {} for template={}'.format(aspect_ratio, template))
            layoutIndex = layoutIndex+1
        return results

    # TODO: asmith 2020/03/03
    # Instinctively I would like to see this moved to the MapReport class with an __eq__ method which
    # would look very much like this one.

    def haveDataSourcesChanged(self, previousReportFile):
        # previousReportFile = '{}-v{}_{}.json'.format(
        #     recipe.mapnumber,
        #     str((version_num-1)).zfill(2),
        #     output_mxd_base
        # )
        # generationRequired = True
        # if (os.path.exists(os.path.join(output_dir, previousReportFile))):
        #     generationRequired = self.haveDataSourcesChanged(os.path.join(output_dir, previousReportFile))

        # returnValue = False
        # with open(previousReportFile, 'r') as myfile:
        #     data = myfile.read()
        #     # parse file
        #     obj = json.loads(data)
        #     for result in obj['results']:
        #         dataFile = os.path.join(self.event.path, (result['dataSource'].strip('/')))
        #         previousHash = result.get('hash', "")
        #         ds = DataSource(dataFile)
        #         latestHash = ds.calculate_checksum()
        #         if (latestHash != previousHash):
        #             returnValue = True
        #             break
        # return returnValue
        return True

    def _do_export(self, recipe):
        """
        Does the actual work of exporting of the PDF, Jpeg and thumbnail files.
        """
        export_dir = recipe.export_metadata.get('exportDirectory', recipe.export_path)

        # When exporting from ArcGIS Pro, we need to set the project as 'CURRENT'
        # in order for it to use the latest context.

        arc_aprx = arcpy.mp.ArcGISProject('CURRENT') \
            if self.useCurrent \
            else \
            arcpy.mp.ArcGISProject(recipe.map_project_path)

        lyt = arc_aprx.listLayouts(recipe.export_metadata.get("layout", None))[0]

        text_element_dict = self.get_text_elements(lyt)

        recipe.export_metadata["datasource"] = text_element_dict.get('data_sources', "")
        recipe.export_metadata["datum"] = text_element_dict.get('spatial_reference', "")
        recipe.export_metadata["donor"] = text_element_dict.get('donor_credit', "")
        recipe.export_metadata["glideno"] = text_element_dict.get('glide_no', "")
        recipe.export_metadata["language"] = text_element_dict.get('language', "")
        recipe.export_metadata["sourceorg"] = self.hum_event.default_source_organisation
        recipe.export_metadata["summary"] = text_element_dict.get('summary', recipe.summary)
        recipe.export_metadata["timezone"] = text_element_dict.get('time_zone', self.hum_event.time_zone)
        recipe.export_metadata["title"] = text_element_dict.get('title', "")

        core_file_name = os.path.splitext(os.path.basename(recipe.map_project_path))[0]
        recipe.core_file_name = core_file_name
        recipe.export_path = export_dir

        now = datetime.now()
        recipe.export_metadata["createdate"] = now.strftime("%Y-%m-%d %H:%M:%S")
        recipe.export_metadata["createtime"] = now.strftime("%H:%M")
        recipe.export_metadata['qclevel'] = recipe.export_metadata.get('qclevel', 'Automatically generated')
        recipe.export_metadata['accessnotes'] = recipe.export_metadata.get('accessnotes', "")

        pdfFileLocation = self.exportPdf(core_file_name, export_dir, arc_aprx, recipe.export_metadata)
        recipe.zip_file_contents.append(pdfFileLocation)
        jpegFileLocation = self.exportJpeg(core_file_name, export_dir, arc_aprx, recipe.export_metadata)
        recipe.zip_file_contents.append(jpegFileLocation)

        if (recipe.export_metadata.get("exportemf", False)):
            emfFileLocation = self.exportEmf(core_file_name, export_dir, arc_aprx, recipe.export_metadata)
            recipe.zip_file_contents.append(emfFileLocation)
        pngThumbNailFileLocation = self.exportPngThumbNail(core_file_name, export_dir, arc_aprx, recipe.export_metadata)
        recipe.zip_file_contents.append(pngThumbNailFileLocation)

        if recipe.atlas or recipe.export_metadata["product-type"] == 'atlas':
            self._export_atlas(recipe, arc_aprx, export_dir, core_file_name)

        maxWidth = 0
        maxHeight = 0

        # Get the extents of the largest "map"
        for mapFrame in (lyt.listElements("MAPFRAME_ELEMENT", "*")):
            extent = mapFrame.map.defaultView.camera.getExtent()
            if (extent.height > maxHeight) and (extent.width > maxWidth):
                maxWidth = extent.width
                maxHeight = extent.height
                recipe.export_metadata["xmin"] = round(extent.XMin, 2)
                recipe.export_metadata["ymin"] = round(extent.YMin, 2)
                recipe.export_metadata["xmax"] = round(extent.XMax, 2)
                recipe.export_metadata["ymax"] = round(extent.YMax, 2)

        recipe.export_metadata['mapNumber'] = recipe.mapnumber
        recipe.export_metadata['productName'] = recipe.product
        recipe.export_metadata['versionNumber'] = recipe.version_num
        recipe.export_metadata['language_iso2'] = self.hum_event.language_iso2

        return recipe

    def _export_atlas(self, recipe, arc_aprx, export_dir, core_file_name):
        """
        Exports each individual page for recipes which contain an atlas definition
        """
        Layout = arc_aprx.listLayouts(recipe.export_metadata.get("layout", None))[0]
        # https://pro.arcgis.com/en/pro-app/arcpy/mapping/mapseries-class.htm

        # exports only the selected pages to a single, multipage PDF file:
        if Layout.mapSeries is not None:
            ms = Layout.mapSeries
            if ms.enabled and (recipe.export_metadata['product-type'] == "atlas"):
                # fields = arcpy.ListFields(fc, 'Flag')
                if (recipe.export_metadata.get("mapBookMode", "Multiple PDF Files") == "Multiple PDF Files"):
                    for pageNum in range(1, ms.pageCount + 1):
                        ms.currentPageNumber = pageNum
                        seriesMapName = getattr(ms.pageRow, ms.pageNameField.name)
                        seriesPdfFileName = core_file_name + "-mapbook-" + seriesMapName + "-" + \
                            recipe.export_metadata.get("pdfresolutiondpi",
                                                       str(self.hum_event.default_pdf_res_dpi)) + "dpi.pdf"
                        seriesPdfFileLocation = os.path.join(export_dir, seriesPdfFileName)
                        ms.exportToPDF(seriesPdfFileLocation, "CURRENT", resolution=int(
                            recipe.export_metadata.get("pdfresolutiondpi", str(self.hum_event.default_pdf_res_dpi))))
                        recipe.zip_file_contents.append(seriesPdfFileLocation)
                else:
                    seriesPdfFileName = core_file_name + "-mapbook-" + \
                        recipe.export_metadata.get("pdfresolutiondpi",
                                                   str(self.hum_event.default_pdf_res_dpi)) + "dpi.pdf"
                    seriesPdfFileLocation = os.path.join(export_dir, seriesPdfFileName)
                    ms.exportToPDF(seriesPdfFileLocation, "ALL", resolution=int(
                        recipe.export_metadata.get("pdfresolutiondpi", str(self.hum_event.default_pdf_res_dpi))))

    def exportJpeg(self, coreFileName, exportDirectory, aprx, exportParams):
        # JPEG
        jpgFileName = coreFileName + "-" + \
            exportParams.get("jpgresolutiondpi", str(self.hum_event.default_jpeg_res_dpi)) + "dpi.jpg"
        jpgFileLocation = os.path.join(exportDirectory, jpgFileName)
        exportParams["jpgfilename"] = jpgFileName
        Layout = aprx.listLayouts(exportParams.get("layout", None))[0]
        Layout.exportToJPEG(jpgFileLocation, resolution=int(exportParams.get(
            "jpgresolutiondpi", str(self.hum_event.default_jpeg_res_dpi))))
        jpgFileSize = os.path.getsize(jpgFileLocation)
        exportParams["jpgfilesize"] = jpgFileSize
        return jpgFileLocation

    def exportPdf(self, coreFileName, exportDirectory, aprx, exportParams):
        # PDF
        pdfFileName = coreFileName + "-" + \
            exportParams.get("pdfresolutiondpi", str(self.hum_event.default_pdf_res_dpi)) + "dpi.pdf"

        pdfFileLocation = os.path.join(exportDirectory, pdfFileName)
        exportParams["pdffilename"] = pdfFileName

        Layout = aprx.listLayouts(exportParams.get("layout", None))[0]
        Layout.exportToPDF(pdfFileLocation, resolution=int(exportParams.get(
            "pdfresolutiondpi", str(self.hum_event.default_pdf_res_dpi))))

        pdfFileSize = os.path.getsize(pdfFileLocation)
        exportParams["pdffilesize"] = pdfFileSize
        return pdfFileLocation

    def exportEmf(self, coreFileName, exportDirectory, aprx, exportParams):
        # EMF
        emfFileName = coreFileName + "-" + \
            exportParams.get("emfresolutiondpi", str(self.hum_event.default_emf_res_dpi)) + "dpi.emf"
        emfFileLocation = os.path.join(exportDirectory, emfFileName)
        exportParams["emffilename"] = emfFileName

        Layout = aprx.listLayouts(exportParams.get("layout", None))[0]
        Layout.exportToEMF(emfFileLocation, resolution=int(exportParams.get(
            "emfresolutiondpi", str(self.hum_event.default_emf_res_dpi))))

        emfFileSize = os.path.getsize(emfFileLocation)
        exportParams["emffilesize"] = emfFileSize
        return emfFileLocation

    def exportPngThumbNail(self, coreFileName, exportDirectory, aprx, exportParams):
        # PNG Thumbnail.  Need to create a larger image first.
        # If this isn't done, the thumbnail is pixelated amd doesn't look good
        pngTmpThumbNailFileName = "tmp-thumbnail.png"
        pngTmpThumbNailFileLocation = os.path.join(exportDirectory, pngTmpThumbNailFileName)

        Layout = aprx.listLayouts(exportParams.get("layout", None))[0]
        Layout.exportToPNG(pngTmpThumbNailFileLocation)

        pngThumbNailFileName = "thumbnail.png"
        pngThumbNailFileLocation = os.path.join(exportDirectory, pngThumbNailFileName)

        # Resize the thumbnail
        fd_img = open(pngTmpThumbNailFileLocation, 'r+b')
        img = Image.open(fd_img)
        img = resizeimage.resize('thumbnail', img, [140, 99])
        img.save(pngThumbNailFileLocation, img.format)
        fd_img.close()

        # Remove the temporary larger thumbnail
        os.remove(pngTmpThumbNailFileLocation)
        return pngThumbNailFileLocation

    def create_output_map_project(self, **kwargs):
        recipe = kwargs['state']
        # Create `mapNumberDirectory` for output
        output_dir = os.path.join(self.cmf.map_projects, recipe.mapnumber)

        if not(os.path.isdir(output_dir)):
            os.mkdir(output_dir)

        # Construct output ArcGIS Pro Project name
        logger.debug('About to create new map project file for product "{}"'.format(recipe.product))
        output_map_base = slugify(recipe.product)
        logger.debug('Set output name for new map project file to "{}"'.format(output_map_base))
        recipe.version_num = self.get_next_map_version_number(output_dir, recipe.mapnumber, output_map_base)
        output_map_name = '{}-v{}-{}{}'.format(
            recipe.mapnumber, str(recipe.version_num).zfill(2), output_map_base, self.get_project_file_extension())
        recipe.map_project_path = os.path.abspath(os.path.join(output_dir, output_map_name))
        logger.debug('Path for new map project file; {}'.format(recipe.map_project_path))
        logger.debug('Map Version number; {}'.format(recipe.version_num))

        output_layout_name = '{}-v{}-{}{}'.format(
            recipe.mapnumber, str(recipe.version_num).zfill(2), output_map_base, self.get_projectfile_extension())

        # Copy `src_template` to `recipe.map_project_path`
        aprxPath = os.path.join(self.cmf.map_templates, 'pro-2.5-blank-project.aprx')
        copyfile(aprxPath, recipe.map_project_path)

        logger.debug('Import template path; {}'.format(recipe.template_path))

        output_layout_path = os.path.abspath(os.path.join(output_dir, output_layout_name))

        # Copy layer file to project path
        copyfile(recipe.template_path, output_layout_path)
        aprx = arcpy.mp.ArcGISProject(recipe.map_project_path)

        aprx.importDocument(output_layout_path)

        aprx.save()

        return recipe
