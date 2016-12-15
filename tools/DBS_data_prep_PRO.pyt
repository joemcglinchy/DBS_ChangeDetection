import arcpy, os, itertools
import numpy as np
import traceback

import arcgisscripting

arcpy.env.overwriteOutput = True

arcpy.CheckOutExtension('spatial')


class Toolbox(object):
    def __init__(self):
        """Define the toolbox (the name of the toolbox is the name of the
        .pyt file)."""
        self.label = "DBS_CD_DataPrep_Toolbox"
        self.alias = "dbsCD"

        # List of tool classes associated with this toolbox
        self.tools = [GenerateSamplePointsFromTruthPoly, ExtractMVfromMD, ReplaceZeroValues, CallMGETModel]


class GenerateSamplePointsFromTruthPoly(object):
    
    # define a helper function
    def getDomainCodes(self, fc):
        
        # get the domain and listing
        input_file_GDB = os.path.dirname(fc)
        domains = arcpy.da.ListDomains(input_file_GDB)
        pairs = []
        vals = []
        for domain in domains:
            # print('Domain name: {0}'.format(domain.name))
            # if domain.domainType == 'CodedValue':
            coded_values = domain.codedValues
            #for val, desc in coded_values.iteritems(): #uncomment for py 2.7
            for val, desc in coded_values.items():
                
                pairs.append((val, desc))
                vals.append(val)

        vals.sort()
        
        return vals # return the list sorted ascending
        
        
    
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "01. Generate Sample Points From Truth Polygons"
        self.description = ""
        self.canRunInBackground = False

    def getParameterInfo(self):
        """Define parameter definitions"""
        param0 = arcpy.Parameter(
            displayName ='Input Truth Data Polygons',
            name ='in_truth_poly',
            datatype ="GPFeatureLayer",
            parameterType ='Required',
            direction ='Input')

        param1 = arcpy.Parameter(
            displayName ='Change Description Codes',
            name ='in_change_codes',
            datatype ="GPString",
            parameterType ='Required',
            direction ='Input')
            
        param1.multiValue=True
        
        param2 = arcpy.Parameter(
            displayName ='Descriptor',
            name ='in_descriptor',
            datatype ="GPString",
            parameterType ='Required',
            direction ='Input')
            
        param3 = arcpy.Parameter(
            displayName ='number of sample points',
            name ='in_numpts',
            datatype ="GPLong",
            parameterType ='Required',
            direction ='Input')
            
        param4 = arcpy.Parameter(
            displayName ='sampling type',
            name ='in_sampl_type',
            datatype ="GPString",
            parameterType ='Required',
            direction ='Input')
            
        param4.filter.list = ['STRATIFIED_RANDOM', 'RANDOM', 'EQUALIZED_STRATIFIED_RANDOM']
            
            
        param5 = arcpy.Parameter(
            displayName = 'output geodatabase',
            name = 'out_gdb',
            datatype = "GPString",
            parameterType = 'Required',
            direction = 'Output')

        params = [param0, param1, param2, param3, param4, param5]
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        
        # param2 = parameters[2]
        
        # get the domain codes
        if parameters[0].valueAsText:
            # if not parameters[1].altered:
            list = self.getDomainCodes(parameters[0].valueAsText)
            # parameters[1].values = list
            parameters[1].filter.list = list
        
        return 

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        
        in_fc =             parameters[0].valueAsText
        change_codes =      parameters[1].values # ; separated string as list of strings
        tag =               parameters[2].valueAsText
        numpts =            parameters[3].value
        samp_type =         parameters[4].valueAsText        
        out_gdb =           parameters[5].valueAsText
        
        
        # check for output GDB
        if not os.path.exists(out_gdb):
            arcpy.AddError("Output workspace does not exist")
            return
            
        DEBUG = False
        
        
        # parse the list and convert to int
        cc = [ int(a) for a in change_codes if len(a) > 0 ]
        
        # check that at least one element is the number 0
        # check that at least one element has been chosen
        if len(cc) < 1:
            arcpy.AddError("please choose at least one change code. Ideally, you would choose the zero-class and one other to compare non-change with another change type")
            return
        
        
        ## iterate through the change types
        pts = []
        for j, val in enumerate(cc):
            
            ## Make a feature layer
            diss_lyr = 'diss_lyr_{}'.format(j)
            wc = "changeDesc = {}".format(val) # TODO: edit
            arcpy.MakeFeatureLayer_management(in_fc, diss_lyr, wc) # TODO:edit
            
            # check if features count is > 0
            
            
            
            
            ## dissolve the feature layer
            diss_fc = 'in_memory/dissol{}'.format(j)
            arcpy.Dissolve_management(diss_lyr, diss_fc)
            
            arcpy.Delete_management(diss_lyr)
            
            ## add fields and calculate
            fields = ["Classname", "Classvalue", "RED", "GREEN", "BLUE"]
            types = ["TEXT", "LONG", "LONG", "LONG", "LONG"]
            vals = ['"placeholder"', 1, 1, 1, 1]
            for i in range(5):
                arcpy.AddField_management(diss_fc, fields[i], types[i])
                arcpy.CalculateField_management(diss_fc, fields[i], vals[i], "PYTHON_9.3")
                
            ## debug, write out fc
            if DEBUG:
                arcpy.CopyFeatures_management(diss_fc, r"C:\Users\jose6641\Documents\arcGIS\Default.gdb\deleteme") 
                
            ## generate sample points
            # numpts = 10000
            temp_pts = "in_memory/pts{}".format(j)
            arcpy.gp.CreateAccuracyAssessmentPoints_sa(diss_fc, temp_pts, "GROUND_TRUTH", "{}".format(numpts), samp_type)
            
            ## add field for change type
            arcpy.AddField_management(temp_pts, "changeDesc2", "LONG")
            arcpy.CalculateField_management(temp_pts, "changeDesc2", val, "PYTHON_9.3")
            
            ## add to list
            pts.append(temp_pts)
            
        ## merge the feature classes
        arcpy.AddMessage(pts)
        pt_name = "AA_pts_{}_{}_{}".format(tag, numpts, samp_type)
        outfc = os.path.join(out_gdb, pt_name)
        arcpy.Merge_management(pts, outfc)
            
        
        
        
        return True
        
class ExtractMVfromMD(object):
              
        
    
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "02. Extract MultiValues to Points from Change GDB mosaic datasets"
        self.description = ""
        self.canRunInBackground = False

    def getParameterInfo(self):
        """Define parameter definitions"""
        inPts = arcpy.Parameter(
            displayName ='Input Truth Data Sample Points',
            name ='in_truth_pts',
            datatype ="GPFeatureLayer",
            parameterType ='Required',
            direction ='Input')

        chMDGDB = arcpy.Parameter(
            displayName ='Change Variable Mosaic GDB',
            name ='in_ch_gdb',
            datatype ="DEType",
            parameterType ='Required',
            direction ='Input')
        
        outPts = arcpy.Parameter(
            displayName ='Output Points',
            name ='out_points',
            datatype ="GPFeatureLayer",
            parameterType ='Required',
            direction ='Output')
            
        params = [inPts, chMDGDB, outPts]
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        
        return 

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        
        fc =                       parameters[0].valueAsText
        image_var_mosaic_gdb =     parameters[1].valueAsText
        out_fc =                   parameters[2].valueAsText
        
        
        arcpy.env.workspace = image_var_mosaic_gdb
            
        # get the mosaic datasets for a specific variable type
        mds	= arcpy.ListDatasets("*_mosaic")

        # construct the field names	
        field_names = [a.split('_mosaic')[0] for a in mds]

        # construct the input parameters for Extract Multi Values to Points
        field_mappings = [[os.path.join(image_var_mosaic_gdb, mds[i]), nm] for i,nm in enumerate(field_names)]
        
        # extract the values
        arcpy.CopyFeatures_management(fc, out_fc)
        arcpy.sa.ExtractMultiValuesToPoints(out_fc, field_mappings, 'BILINEAR')	
        
        
        return True     

        
class ReplaceZeroValues(object):
    
           
        
    
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "03. Replace Zero Values"
        self.description = ""
        self.canRunInBackground = False

    def getParameterInfo(self):
        """Define parameter definitions"""
        inPts = arcpy.Parameter(
            displayName ='Input Truth Data Sample Points',
            name ='in_truth_pts',
            datatype ="GPFeatureLayer",
            parameterType ='Required',
            direction ='Input')

        replaceType = arcpy.Parameter(
            displayName ='Replacement Method',
            name ='in_rep_method',
            datatype ="GPString",
            parameterType ='Required',
            direction ='Input')
        replaceType.filter.list = ['mean', 'median']
        replaceType.value = 'mean'
        
        outPts = arcpy.Parameter(
            displayName ='Output Points',
            name ='out_points',
            datatype ="GPFeatureLayer",
            parameterType ='Required',
            direction ='Output')
            
        params = [inPts, replaceType, outPts]
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        
        return 

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        
        fc =      parameters[0].valueAsText
        rep =     parameters[1].valueAsText
        out_fc =  parameters[2].valueAsText
        
        
        # check for output GDB
        out_gdb = os.path.dirname(out_fc)
        if not os.path.exists(out_gdb):
            arcpy.AddWarning("Output workspace does not exist. Creating..")
            out_dir = os.path.dirname(out_gdb)
            gdb = os.path.basename(out_gdb)
            arcpy.CreateFileGDB_management(out_dir, gdb)
            
        # do the replacement
        sr = arcpy.Describe(fc).spatialReference
        fc_copy = "{}_{}".format("in_memory/", rep)
        arcpy.CopyFeatures_management(fc, fc_copy)
        flds = arcpy.ListFields(fc)
        field_names = [f.name for f in flds]
        f_arr = arcpy.da.FeatureClassToNumPyArray(fc_copy, ['SHAPE@XY'] + field_names)

        if rep.lower() == 'mean':
            for i,field in enumerate(field_names):
                if flds[i].type.upper() == "DOUBLE":
                    arcpy.AddMessage('processing field: {}'.format(field))
                    arr = f_arr[field].copy()
                    mean_rep = np.nanmean(arr[arr!=0])                 
                    f_arr[field][f_arr[field] == 0] = mean_rep
                    f_arr[field][np.isnan(f_arr[field])] = mean_rep

                    num_nan_rep = len(arr[np.isnan(arr)]) - len(f_arr[field][np.isnan(f_arr[field])])
                    num_zero_rep = len(arr[arr==0]) - len(f_arr[field][f_arr[field] == 0])
                    
                    arcpy.AddMessage("replaced {} zero values".format(num_zero_rep))
                    arcpy.AddMessage("replaced {} NaN values".format(num_nan_rep))

        if rep.lower() == 'median':
            for i,field in enumerate(field_names):
                if flds[i].type.upper() == "DOUBLE":
                    arcpy.AddMessage('processing field: {}'.format(field))
                    
                    arr = f_arr[field].copy()
                    median_rep = np.nanmedian(arr[arr!=0])
                    f_arr[field][f_arr[field] == 0] = median_rep
                    f_arr[field][np.isnan(f_arr[field])] = median_rep
                    
                    num_nan_rep = len(arr[np.isnan(arr)]) - len(f_arr[field][np.isnan(f_arr[field])])
                    num_zero_rep = len(arr[arr==0]) - len(f_arr[field][f_arr[field] == 0])
                    
                    arcpy.AddMessage("replaced {} zero values".format(num_zero_rep))
                    arcpy.AddMessage("replaced {} NaN values".format(num_nan_rep))
                    
                    

        arcpy.da.NumPyArrayToFeatureClass(f_arr, out_fc, ['SHAPE@XY'], sr)


        # all data should now be prepped for any modeling algorithm. All data ranges are the same and there
        # are no zero valued samples since they have been replaced by both the mean and median value of the 
        # samples for each variable.
        
        
        
        return True        
        
class CallMGETModel(object):
    
           
        
    
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "04. Call MGET Model"
        self.description = ""
        self.canRunInBackground = False

    def getParameterInfo(self):
        """Define parameter definitions"""
        inPts = arcpy.Parameter(
            displayName ='Input Truth Data Sample Points',
            name ='in_truth_pts',
            datatype ="GPFeatureLayer",
            parameterType ='Required',
            direction ='Input')

        modelType = arcpy.Parameter(
            displayName ='Model Type',
            name ='in_model_method',
            datatype ="GPString",
            parameterType ='Required',
            direction ='Input')
        modelType.filter.list = ['GAM', 'others not wrapped']
        modelType.value = 'GAM'
        
        out_folder = arcpy.Parameter(
            displayName ='Output Model Fit Folder',
            name ='out_folder',
            datatype ="DEType",
            parameterType ='Required',
            direction ='Output')
            
        params = [inPts, modelType, out_folder]
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        
        return 

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        
        # helper function
        def getCombs(arr):
        
            combs=[]
            for L in range(0, len(arr) +1):
                for subset in itertools.combinations(arr, L):
                    combs.append(subset)
                    
            return combs
        
        arcpy.AddMessage("entered script")
        
        # specify path to MGET toolbox
        mget_path = r"C:\Program Files\GeoEco\ArcGISToolbox\Marine Geospatial Ecology Tools.tbx"
        try:
            arcpy.AddMessage("importing toolbox")
            # arcpy.ImportToolbox(mget_path,"GeoEco")
            gp = arcgisscripting.create()
            gp.AddToolbox(mget_path, "GeoEco")
            
        except Exception as e:
            arcpy.AddError(e.message)
            
            # Get the traceback object
            tb = sys.exc_info()[2]
            tbinfo = traceback.format_tb(tb)[0]

            # Concatenate information together concerning the error into a message string
            pymsg = "PYTHON ERRORS:\nTraceback info:\n" + tbinfo + "\nError Info:\n" + str(sys.exc_info()[1])

            # Print Python error messages for use in Python / Python Window
            arcpy.AddError(pymsg + "\n")
            
            return
        
        # gather parameters
        arcpy.AddMessage("gathering parameters")
        fc =      parameters[0].valueAsText
        model =   parameters[1].valueAsText
        out_dir = parameters[2].valueAsText
        
        try:
            # check for output folder
            if os.path.exists(out_dir):
                arcpy.AddMessage("directory exists...")
            else:
                arcpy.AddWarning("Output folder does not exist. Creating..")
                os.mkdir(out_dir)
                
            # add the binomial test variable to an in_memory feature set
            arcpy.AddMessage("copy feature class")
            fc_test = "in_memory/test_fc"
            arcpy.CopyFeatures_management(fc, fc_test)
            arcpy.AddField_management(fc_test, "TEST", "DOUBLE")

            # calculate the test feature based on change code
            arcpy.AddMessage("changing classification codes")
            wc_change = "changeDesc2 <> 0"
            templyr = 'templyr'
            arcpy.MakeFeatureLayer_management(fc_test, templyr)
            arcpy.SelectLayerByAttribute_management(templyr, "NEW_SELECTION", wc_change)
            arcpy.CalculateField_management(templyr, "TEST", 1, "PYTHON_9.3")

            wc_noChange = "changeDesc2 = 0"
            arcpy.SelectLayerByAttribute_management(templyr, "NEW_SELECTION", wc_noChange)
            arcpy.CalculateField_management(templyr, "TEST", 0, "PYTHON_9.3")

            # clear the selection
            arcpy.AddMessage("clearing selection")
            arcpy.SelectLayerByAttribute_management(templyr,"CLEAR_SELECTION")

            # DEBUG
            arcpy.AddMessage("copying to disk...")
            temp_fc = "in_memory/temp_fc"
            arcpy.CopyFeatures_management(templyr, temp_fc)

            # get field names for model fitting. TEST will be the last field added, so don't look at it
            flds = arcpy.ListFields(temp_fc)
            field_names = [f.name for f in flds[:-1] if (f.type.upper() == "DOUBLE" and ("SHAPE" not in f.name.upper()))]

            # #construct the string for the python call
            # contPreds = ""
            # for v in field_names:
                # contPreds += "{} # # #;".format(v)
                
            # # strip the last semicolon
            # contPreds = contPreds[:-1]
            
            arcpy.AddMessage("calling MGET")
            
            # if import toolbox worked, use arcpy.GAMFitToArcGISTable_GeoEco() otherwise...
            var_combs = getCombs(field_names)
            
            for i,com in enumerate(var_combs):
            
                if len(com)>1:
                    arcpy.AddMessage("on iteration {} with variables {}\n".format(i+1, com))
                
                    model_dir = "model_{}_{}".format(model, i)
                    model_fol = os.path.join(out_dir, model_dir)
                    if not os.path.exists(model_fol):
                        os.mkdir(model_fol)
                        
                    rdatafile = "{}_{}.RData".format(model, i)
                    outModelFile = os.path.join(model_fol, rdatafile)
                    
                    contPreds = ""
                    for v in com:
                        contPreds += "{} # # #;".format(v)
                        
                    # strip the last semicolon
                    contPreds = contPreds[:-1]                    
                    
                    # gp.GAMFitToArcGISTable_GeoEco(inputTable=templyr, outputModelFile="V:/DBS_ChangeDetection/MGET_models/test/GAM_fit_test.RData", responseVariable="TEST", family="binomial", rPackage="mgcv", continuousPredictors="grayStats_corr # # #;grayStats_energy # # #;grayStats_entropy # # #;grayStats_kurtosis # # #;grayStats_skewness # # #;grayStats_mean # # #;grayStats_variance # # #", categoricalPredictors="",offsetVariable="", offsetTransform="",bivariateInteractions="",where="",link="",variance="",theta="", method="GCV.Cp",optimizer="outer",alternativeOptimizer="newton",select="false",gamma="1",selectionMethod="",logSelectionDetails="true", writeSummaryFile="true",writeDiagnosticPlots="true",writeTermPlots="true",residuals="false",xAxis="true",commonScale="true",plotFileFormat="png",res="1000",width="3000",height="3000", pointSize="10", bg="white")
                    gp.GAMFitToArcGISTable_GeoEco(templyr, outModelFile, "TEST", "binomial", "mgcv", contPreds)                
            
            
            
        
        except Exception as e:
            arcpy.AddError(e.message)
            arcpy.AddError(arcpy.GetMessages())
            
            # Get the traceback object
            tb = sys.exc_info()[2]
            tbinfo = traceback.format_tb(tb)[0]

            # Concatenate information together concerning the error into a message string
            pymsg = "PYTHON ERRORS:\nTraceback info:\n" + tbinfo + "\nError Info:\n" + str(sys.exc_info()[1])

            # Print Python error messages for use in Python / Python Window
            arcpy.AddError(pymsg + "\n")
            return
        
        return    