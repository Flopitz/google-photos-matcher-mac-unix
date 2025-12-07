# Google Photos Matcher Mac/Unix - Copyright (c) 2025 Marco Trinastich
# Licensed under GNU GPL v3 - see LICENSE file for details

from auxFunctions import *
import json
from PIL import Image
import sys
import logging

piexifCodecs = [k.casefold() for k in ['TIF', 'TIFF', 'JPEG', 'JPG']]
piexifCodecsToConvert = [k.casefold() for k in ['TIF', 'TIFF']]
piexifCodecsToRename = [k.casefold() for k in ['JPEG']]
videoCodecs = [k.casefold() for k in ['MP4', 'MOV']]
    
DEFAULT_FOLDER = "/home/florian/DataPartition/Takeout-2025-11-30/Takeout/"

def process(browserPath, editedW, convertAll, convertIfNeeded):    
    mediaMoved = []  # array with names of all the media already matched
    path = browserPath or DEFAULT_FOLDER # source path
    fixedMediaPath = path + "/MatchedMedia"  # destination path
    nonEditedMediaPath = path + "/EditedRaw"
    errorCounter = 0
    successCounter = 0
    editedWord = editedW or "edited"
    convertAll = convertAll or False
    convertIfNeeded = convertIfNeeded or True

    # Setup logging
    log_file = os.path.join(path, "google_photos_matcher.log")
    
    # Reset handlers to avoid duplicate logs if run multiple times in same session (unlikely but safe)
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
        
    logging.basicConfig(
        filename=log_file,
        filemode='a',
        format='%(asctime)s - %(levelname)s - %(message)s',
        level=logging.WARNING
    )
    
    print(f"Logging errors to: {log_file}")

    json_files = []
    for dirpath, _, filenames in os.walk(path):
        if dirpath == fixedMediaPath or dirpath == nonEditedMediaPath:
            continue
        for filename in filenames:
            if filename.endswith(".json"):
                json_files.append(os.path.join(dirpath, filename))

    json_files.sort(key=lambda s: len(os.path.basename(s)))

    total_files = len(json_files)
    for i, json_path in enumerate(json_files):
            dirpath = os.path.dirname(json_path)
            json_filename = os.path.basename(json_path)
            with open(json_path, encoding="utf8") as f:  # Load JSON into a var
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    msg = f"Warning: Could not decode JSON from {json_path}. Skipping."
                    print(msg)
                    logging.warning(msg)
                    continue

            progress = round((i + 1) / total_files * 100, 2)
            print(str(progress) + "%")

            if 'title' not in data:
                msg = f"Warning: Skipping {json_path} because it does not contain a 'title' field."
                print(msg)
                logging.warning(msg)
                continue
            titleOriginal = data['title']  # Store metadata into vars
            if isinstance(titleOriginal, list):
                if len(titleOriginal) > 0:
                    titleOriginal = str(titleOriginal[0])
                else:
                    titleOriginal = "Unknown"

            try:
                result = searchMedia(dirpath, titleOriginal, mediaMoved, nonEditedMediaPath, editedWord)
                title = result[0]
                movedTitle = result[1]
                movedFilePath = result[2]

            except Exception as e:
                msg = "Error on searchMedia() with file " + titleOriginal
                print(msg)
                logging.error(msg, exc_info=True)
                errorCounter += 1
                continue

            filepath = dirpath + "/" + title
            if title == "None":
                msg = "Error: " + titleOriginal + " not found"
                print(msg)
                logging.error(msg)
                errorCounter += 1
                continue
            
            # TARGET MEDIA METADATA EDIT
            filepath = updateFileMetadata(data, filepath, title, convertAll, convertIfNeeded)
            if filepath is None:
                logging.error(f"Failed to update metadata for {titleOriginal}")
                errorCounter += 1
                continue
            
            #MOVE FILE AND DELETE JSON
            # os.replace(filepath, fixedMediaPath + "/" + title)
            try:
                os.remove(json_path)
            except OSError as e:
                msg = f"Error deleting JSON {json_path}: {e}"
                print(msg)
                logging.error(msg)
                
            mediaMoved.append(title)
            successCounter += 1
            
            # ORIGINAL MEDIA METADATA EDIT (IF ANY) 
            if not movedFilePath == "None" and not movedTitle == "None":
                if updateFileMetadata(data, movedFilePath, movedTitle, convertAll, convertIfNeeded) is None:
                    errorCounter += 1
                else:
                    successCounter += 1
                    mediaMoved.append(movedTitle)
            
            # RELATED VIDEO METADATA EDIT (IN CASE OF HEIC)
            filePathName = filepath.rsplit('.', 1)[0]
            fileName = title.rsplit('.', 1)[0].casefold()
            fileExtension = title.rsplit('.', 1)[1].casefold()        
            if fileExtension == "heic".casefold():
                # in case of HEIC (Apple iOS dynamic photos) update related MP4 metadata as well
                mp4FilePath = filePathName + ".MP4"
                mp4Title = fileName + ".MP4"
                if os.path.exists(mp4FilePath):
                    if updateFileMetadata(data, mp4FilePath, mp4Title, False, False) is None:
                        errorCounter += 1
                    else:
                        # os.replace(mp4FilePath, fixedMediaPath + "/" + mp4Title)
                        successCounter += 1

            
    sucessMessage = " successes"
    errorMessage = " errors"

    #UPDATE INTERFACE
    if successCounter == 1:
        sucessMessage = " success"

    if errorCounter == 1:
        errorMessage = " error"

    print(str(100) + "%")
    print("\nMatching process finished with " + str(successCounter) + sucessMessage + " and " + str(errorCounter) + errorMessage + ".")


def updateFileMetadata(data, filepath, title, convertAll, convertIfNeeded):
    # METADATA EDIT
    timeStamp = int(data['photoTakenTime']['timestamp'])  # Get creation time
    print(filepath)
    
    filePathName = filepath.rsplit('.', 1)[0]
    fileExtension = title.rsplit('.', 1)[1].casefold()        
            
    if fileExtension in piexifCodecs:  # If PIEXIF is supported (images only)
        # Convert/rename to jpg
        converted = False
        if convertAll or fileExtension in piexifCodecsToConvert:
            filepath = convertToJpg(filepath, filePathName, title)
            converted = True
        elif fileExtension in piexifCodecsToRename:
            filepath = renameToJpg(filepath, filePathName, title)
        
        if filepath is None:
            # Error converting/renaming to jpg
            return None
        
        error = set_Images_EXIF_Managed(filepath, data['geoData']['latitude'], data['geoData']['longitude'], data['geoData']['altitude'], timeStamp)
        
        # If failed for not a JPEG error, try to convert to JPG (if it wasn't done before)
        if convertIfNeeded and not error is None and not converted and str(error).casefold() == "Given data isn't JPEG.".casefold():
            filepath = convertToJpg(filepath, filePathName, title)
            if filepath is None:
                # Error converting/renaming to jpg
                return None
                
            # Retry set_EXIF with converted file
            error = set_Images_EXIF_Managed(filepath, data['geoData']['latitude'], data['geoData']['longitude'], data['geoData']['altitude'], timeStamp)
        
        # Error handler
        if not error is None:
            msg = "Error: Inexistent EXIF data for " + filepath + ": " + str(error)
            print(msg)
            logging.error(msg)
            return None
    
    if fileExtension in videoCodecs:  # If Video Codec is detected try to set gps exif with exiftool if needed
        set_QuickTime_Video_EXIF(filepath, data['geoData']['latitude'], data['geoData']['longitude'], data['geoData']['altitude'])
    
    setFileTime(filepath, timeStamp) #File creation and modification time
    
    return filepath


def set_Images_EXIF_Managed(filepath, lat, lng, altitude, timeStamp):
    try:
        set_Images_EXIF(filepath, lat, lng, altitude, timeStamp)
        return None
    except Exception as e:  # Error handler        
        return e


def convertToJpg(filepath, filePathName, title):
    try:
        # Open and convert img to jpg
        im = Image.open(filepath)
        
        # Rename to jpg
        filepath = renameToJpg(filepath, filePathName, title)
        if filepath is None:
            # Error renaming to jpg
            return None
        
        # Save img
        try:
            im.save(filepath, format='jpeg', exif=im.getexif())
        except Exception:
            msg = f"Warning: Could not preserve EXIF for {title}, saving without EXIF."
            print(msg)
            logging.warning(msg)
            im.save(filepath, format='jpeg')
        
        #rgb_im = im.convert('RGB')
        #rgb_im.save(filepath)
        
        return filepath
    except Exception as e:
        msg = "Error converting to JPG in " + title + ": " + str(e)
        print(msg)
        logging.error(msg)
        return None

def renameToJpg(filepath, filePathName, title):
    try:
        # Rename img to jpg
        os.replace(filepath, filePathName + ".jpg")
        filepath = filePathName + ".jpg"
        return filepath
    except ValueError as e:
        msg = "Error renaming to JPG in " + title
        print(msg)
        logging.error(msg)
        return None


## Application

def showAppHeader(folder, editedW, convertAll, convertIfNeeded):
    # App header and parameter recap
    print("===================================")
    print(" Google Photos Matcher Mac/Unix ")
    print("===================================")
    print("Parameters Recap:")
    print(f"  - Target Folder: {folder}")
    print(f"  - Edited Word: {editedW if editedW else 'Default (edited)'}")
    print(f"  - Convert All to JPG: {convertAll if convertAll is not None else 'Default (False)'}")
    print(f"  - Convert If Needed: {convertIfNeeded if convertIfNeeded is not None else 'Default (True)'}")
    print("===================================\n")

def showErrorAndLegend():
    # Show error and usage legend
    print("===================================")
    print(" Google Photos Matcher Mac/Unix ")
    print("===================================\n")
    print("Error: No folder specified.\n\n")
    print("Usage: ./run.sh <target_folder> [edited_word] [convert_all_to_jpg] [convert_if_needed]\n")
    print("Arguments:")
    print("  <target_folder>       Path to the folder containing JSON and media files.")
    print("  [edited_word]         (Optional) Suffix for edited media. Default: 'edited'.")
    print("  [convert_all_to_jpg]  (Optional) Convert all images to JPG. Default: False.")
    print("  [convert_if_needed]   (Optional) Convert images to JPG if metadata editing fails. Default: True.\n\n")

def readArgs():
    folder = None
    if len(sys.argv) > 1:
        folder = sys.argv[1]
    
    editedW = sys.argv[2] if len(sys.argv) > 2 else None

    convertAll = None
    if len(sys.argv) > 3:
        if sys.argv[3].casefold() == "true".casefold():
            convertAll = True
        elif sys.argv[3].casefold() == "false".casefold():
            convertAll = False
    
    convertIfNeeded = None
    if len(sys.argv) > 4:
        if sys.argv[4].casefold() == "true".casefold():
            convertIfNeeded = True
        elif sys.argv[4].casefold() == "false".casefold():
            convertIfNeeded = False
    
    return [folder, editedW, convertAll, convertIfNeeded]

def appInit():
    [folder, editedW, convertAll, convertIfNeeded] = readArgs()
    showAppHeader(folder, editedW, convertAll, convertIfNeeded)
    process(folder, editedW, convertAll, convertIfNeeded)
        
appInit()                                                        