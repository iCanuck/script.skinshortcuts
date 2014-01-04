import os, sys
import xbmc, xbmcaddon, xbmcgui, xbmcplugin, urllib, xbmcvfs
import xml.etree.ElementTree as xmltree
from time import gmtime, strftime
from datetime import datetime
from traceback import print_exc

if sys.version_info < (2, 7):
    import simplejson
else:
    import json as simplejson

__addon__        = xbmcaddon.Addon()
__addonid__      = __addon__.getAddonInfo('id')
__addonversion__ = __addon__.getAddonInfo('version')
__language__     = __addon__.getLocalizedString
__cwd__          = __addon__.getAddonInfo('path').decode("utf-8")
__addonname__    = __addon__.getAddonInfo('name').decode("utf-8")
__resource__   = xbmc.translatePath( os.path.join( __cwd__, 'resources', 'lib' ).encode("utf-8") ).decode("utf-8")
__datapath__     = os.path.join( xbmc.translatePath( "special://profile/addon_data/" ).decode('utf-8'), __addonid__ )
__profilepath__  = xbmc.translatePath( "special://profile/" ).decode('utf-8')
__skinpath__     = xbmc.translatePath( "special://skin/shortcuts/" ).decode('utf-8')
__defaultpath__  = xbmc.translatePath( os.path.join( __cwd__, 'resources', 'shortcuts').encode("utf-8") ).decode("utf-8")

sys.path.append(__resource__)

def log(txt):
    if isinstance (txt,str):
        txt = txt.decode('utf-8')
    message = u'%s: %s' % (__addonid__, txt)
    xbmc.log(msg=message.encode('utf-8'), level=xbmc.LOGDEBUG)
        
class Main:
    # MAIN ENTRY POINT
    def __init__(self):
        self._parse_argv()
        self.WINDOW = xbmcgui.Window(10000)
        
        # Create datapath if not exists
        if not xbmcvfs.exists(__datapath__):
            xbmcvfs.mkdir(__datapath__)
        
        # Perform action specified by user
        if not self.TYPE:
            line1 = "This addon is for skin developers, and requires skin support"
            xbmcgui.Dialog().ok(__addonname__, line1)
            
        if self.TYPE=="launch":
            self._launch_shortcut( self.PATH )
        if self.TYPE=="manage":
            self._manage_shortcuts( self.GROUP )
        if self.TYPE=="list":
            self._list_shortcuts( self.GROUP )
        if self.TYPE=="settings":
            self._manage_shortcut_links()            
        if self.TYPE=="resetall":
            self._reset_all_shortcuts()
    
    def _parse_argv( self ):
        try:
            params = dict( arg.split( "=" ) for arg in sys.argv[ 1 ].split( "&" ) )
            self.TYPE = params.get( "type", "" )
        except:
            try:
                params = dict( arg.split( "=" ) for arg in sys.argv[ 2 ].split( "&" ) )
                self.TYPE = params.get( "?type", "" )
            except:
                params = {}
        
        self.GROUP = params.get( "group", "" )
        self.PATH = params.get( "path", "" )
    
    
    # PRIMARY FUNCTIONS
    def _launch_shortcut( self, path ):
        log( "### Launching shortcut" )
        
        runDefaultCommand = True
        paths = [os.path.join( __profilepath__ , "overrides.xml" ),os.path.join( __skinpath__ , "overrides.xml" )]
        action = urllib.unquote( self.PATH )
        for path in paths:
            if xbmcvfs.exists( path ) and runDefaultCommand:    
                trees = [self._load_overrides_skin(), self._load_overrides_user()]
                log( trees )
                for tree in trees:
                    if tree is not None:
                        tree = xmltree.parse( path )
                        # Search for any overrides
                        elems = tree.findall( 'override' )
                        for elem in elems:
                            if elem.attrib.get( 'action' ) == action:
                                runCustomCommand = True
                                
                                # Check any conditions
                                conditions = elem.findall('condition')
                                for condition in conditions:
                                    if xbmc.getCondVisibility( condition.text ) == False:
                                        runCustomCommand = False
                                        break
                                
                                # If any and all conditions have been met, run actions
                                if runCustomCommand == True:
                                    actions = elem.findall( 'action' )
                                    for action in actions:
                                        log( "Override action: " + action.text )
                                        runDefaultCommand = False
                                        xbmc.executebuiltin( action.text )
                                    break
        
        # If we haven't overridden the command, run the original
        if runDefaultCommand == True:
            xbmc.executebuiltin( urllib.unquote(self.PATH) )
            
        # Tell XBMC not to try playing any media
        xbmcplugin.setResolvedUrl( handle=int( sys.argv[1]), succeeded=False, listitem=xbmcgui.ListItem() )
        
    def _manage_shortcuts( self, group ):
        import gui
        ui= gui.GUI( "script-skinshortcuts.xml", __cwd__, "default", group=group )
        ui.doModal()
        del ui
        # Update home window property (used to automatically refresh type=settings)
        xbmcgui.Window( 10000 ).setProperty( "skinshortcuts",strftime( "%Y%m%d%H%M%S",gmtime() ) )
        
        # Clear window properties for this group
        xbmcgui.Window( 10000 ).clearProperty( "skinshortcuts-" + group )
        
        # Check for settings
        self.checkForSettings()
        
    def _get_shortcuts( self, group ):
        # This will load the shortcut file, and save it as a window property
        # Additionally, if the override files haven't been loaded, we'll load them too
        
        # If we've not loaded this shortcut group...
        if not xbmcgui.Window( 10000 ).getProperty( "skinshortcuts-" + group ):
            log( "### LOADING SHORTCUTS FROM FILE ###" )
            
            # Set path based on existance of user defined shortcuts, then skin-provided, then script-provided
            if xbmcvfs.exists( os.path.join( __datapath__ , group + ".shortcuts" ) ):
                # User defined shortcuts
                path = os.path.join( __datapath__ , group + ".shortcuts" )
            elif xbmcvfs.exists( os.path.join( __skinpath__ , group + ".shortcuts" ) ):
                # Skin-provided defaults
                path = os.path.join( __skinpath__ , group + ".shortcuts" )
            elif xbmcvfs.exists( os.path.join( __defaultpath__ , group + ".shortcuts" ) ):
                # Script-provided defaults
                path = os.path.join( __defaultpath__ , group + ".shortcuts" )
            else:
                # No custom shortcuts or defaults available
                path = ""
                
            # If no path was found ... (this means there are no shortcuts for this group)
            if path == "":
                log( "### - NO SHORTCUTS FOUND" )
                # Save an empty array to the global property
                xbmcgui.Window( 10000 ).setProperty( "skinshortcuts-" + group, simplejson.dumps( [] ) )
            else:
                log( "### FILE CONTAINING SHORTCUTS FOUND ###" )
                # We've found a file containing shortcuts
                try:
                    # Try loading shortcuts
                    log ("### LOADING SHORTCUTS FILE ###" )
                    file = xbmcvfs.File( path )
                    log( "### PROCESSING SHORTCUTS FILE ###" )
                    unprocessedList = eval( file.read() )
                    file.close
                    processedList = self._process_shortcuts( unprocessedList, group )
                    log ( processedList )
                    xbmcgui.Window( 10000 ).setProperty( "skinshortcuts-" + group, simplejson.dumps( processedList ) )
                except:
                    print_exc()
                    log( "### ERROR could not load file %s" % path )
                    xbmcgui.Window( 10000 ).setProperty( "skinshortcuts-" + group, simplejson.dumps( [] ) )
                    
        else:
            log( "### SHORTCUTS ALREADY LOADED ###" )

        # Return this shortcut group
        return simplejson.loads( xbmcgui.Window( 10000 ).getProperty( "skinshortcuts-" + group ) )
        
    def _process_shortcuts( self, listitems, group ):
        # This function will process any graphics overrides provided by the skin, and return a set of listitems ready to be stored
        tree = self._load_overrides_skin()
        returnitems = []
        
        for item in listitems:
            # Generate the labelID
            label = item[0]
            labelID = item[0].replace(" ", "").lower()
            
            # Localize label & labelID
            if not label.find( "::SCRIPT::" ) == -1:
                labelID = self.createNiceName( label[10:] )
                label = __language__(int( label[10:] ) )
            elif not label.find( "::LOCAL::" ) == -1:
                labelID = self.createNiceName( label[9:] )
                label = xbmc.getLocalizedString(int( label[9:] ) )
            
            # If the user hasn't overridden the thumbnail, check for skin override
            if not len(item) == 6 or (len(item) == 6 and item[5] == "True"):
                if tree is not None:
                    elems = tree.findall('thumbnail')
                    for elem in elems:
                        if elem is not None and elem.attrib.get( 'labelID' ) == labelID:
                            item[3] = elem.text
                        if elem is not None and elem.attrib.get( 'image' ) == item[3]:
                            item[3] = elem.text
                        if elem is not None and elem.attrib.get( 'image' ) == item[2]:
                            item[2] = elem.text
            
            # Add item
            returnitems.append( [label, item[1], item[2], item[3], item[4], labelID] )
            #returnitems.append( item )
                
        return returnitems
                
    def _load_overrides_skin( self ):
        # If we haven't already loaded skin overrides, or if the skin has changed, load the overrides file
        if not xbmcgui.Window( 10000 ).getProperty( "skinshortcuts-overrides-skin" ) or not xbmcgui.Window( 10000 ).getProperty( "skinshortcuts-overrides-skin" ) == __skinpath__:
            xbmcgui.Window( 10000 ).setProperty( "skinshortcuts-overrides-skin", __skinpath__ )
            overridepath = os.path.join( __skinpath__ , "overrides.xml" )
            if xbmcvfs.exists(overridepath):
                try:
                    file = xbmcvfs.File( overridepath )
                    xbmcgui.Window( 10000 ).setProperty( "skinshortcuts-overrides-skin-data", simplejson.dumps( file.read().encode( 'utf-8' ) ) )
                    file.close
                except:
                    print_exc()
                    xbmcgui.Window( 10000 ).setProperty( "skinshortcuts-overrides-skin-data", "No overrides" )
            else:
                xbmcgui.Window( 10000 ).setProperty( "skinshortcuts-overrides-skin-data", "No overrides" )
        else:
            log( "### SKIN OVERRIDES ALREADY LOADED ###" )
                
        # Return the overrides
        returnData = xbmcgui.Window( 10000 ).getProperty( "skinshortcuts-overrides-skin-data" )
        if returnData == "No overrides":
            return None
        else:
            return xmltree.fromstring( simplejson.loads( returnData ) )
            
    def _load_overrides_user( self ):
        # If we haven't already loaded user overrides
        if not xbmcgui.Window( 10000 ).getProperty( "skinshortcuts-overrides-user" ):
            log( "### LOADING USER OVERRIDES FROM FILE ###" )
            xbmcgui.Window( 10000 ).setProperty( "skinshortcuts-overrides-user", __profilepath__ )
            overridepath = os.path.join( __profilepath__ , "overrides.xml" )
            if xbmcvfs.exists(overridepath):
                try:
                    file = xbmcvfs.File( overridepath )
                    xbmcgui.Window( 10000 ).setProperty( "skinshortcuts-overrides-user-data", simplejson.dumps( file.read().encode( 'utf-8' ) ) )
                    file.close
                except:
                    print_exc()
                    xbmcgui.Window( 10000 ).setProperty( "skinshortcuts-overrides-user-data", "No overrides" )
            else:
                xbmcgui.Window( 10000 ).setProperty( "skinshortcuts-overrides-user-data", "No overrides" )
        else:
            log( "### USER OVERRIDES ALREADY LOADED ###" )
                
        # Return the overrides
        returnData = xbmcgui.Window( 10000 ).getProperty( "skinshortcuts-overrides-user-data" )
        if returnData == "No overrides":
            return None
        else:
            return xmltree.fromstring( simplejson.loads( returnData ) )
            
    def _list_shortcuts( self, group ):
        log( "### Listing shortcuts ..." )
        if group == "":
            log( "### - NO GROUP PASSED")
            # Return an empty list
            xbmcplugin.endOfDirectory(handle=int(sys.argv[1]))
            return None
            
        # Load shortcuts and overrides
        listitems = self._get_shortcuts( group )
        
        for item in listitems:
            # Generate a listitem
            path = sys.argv[0] + "?type=launch&path=" + item[4] + "&group=" + self.GROUP
            
            listitem = xbmcgui.ListItem(label=item[0], label2=item[1], iconImage=item[2], thumbnailImage=item[3])
            
            listitem.setProperty('IsPlayable', 'True')
            listitem.setProperty( "labelID", item[5] )
            listitem.setProperty( "action", urllib.unquote( item[4] ) )
            listitem.setProperty( "group", group )
            listitem.setProperty( "path", path )
            
            # Localize label2 (type of shortcut)
            if not listitem.getLabel2().find( "::SCRIPT::" ) == -1:
                listitem.setLabel2( __language__( int( listitem.getLabel2()[10:] ) ) )
                            
            # Add item
            if group == "mainmenu":
                if self.checkVisibility( listitem.getProperty( 'labelID' ) ):
                    xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=path, listitem=listitem)
            else:
                xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=path, listitem=listitem)
            
        xbmcplugin.endOfDirectory(handle=int(sys.argv[1]))
        
        # Set window property if no settings shortcut and we're listing mainmenu
        if group == "mainmenu":
            file_path = os.path.join( __datapath__, "nosettings.info")
            if xbmcvfs.exists( file_path ):
                xbmcgui.Window( 10000 ).setProperty( "SettingsShortcut","False" )
            else:
                xbmcgui.Window( 10000 ).setProperty( "SettingsShortcut","True" ) 
    
    def _manage_shortcut_links ( self ):
        log( "### Generating list for skin settings" )
        
        # Create link to manage main menu
        path = sys.argv[0] + "?type=launch&path=" + urllib.quote( "RunScript(script.skinshortcuts,type=manage&group=mainmenu)" )
        listitem = xbmcgui.ListItem(label=__language__(32035), label2="", iconImage="DefaultShortcut.png", thumbnailImage="DefaultShortcut.png")
        listitem.setProperty('isPlayable', 'False')
        xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=path, listitem=listitem, isFolder=False)
        
        # Set path based on user defined mainmenu, then skin-provided, then script-provided
        if xbmcvfs.exists( os.path.join( __datapath__ , "mainmenu.shortcuts" ) ):
            # User defined shortcuts
            path = os.path.join( __datapath__ , "mainmenu.shortcuts" )
        elif xbmcvfs.exists( os.path.join( __skinpath__ , "mainmenu.shortcuts" ) ):
            # Skin-provided defaults
            path = os.path.join( __skinpath__ , "mainmenu.shortcuts" )
        elif xbmcvfs.exists( os.path.join( __defaultpath__ , "mainmenu.shortcuts" ) ):
            # Script-provided defaults
            path = os.path.join( __defaultpath__ , "mainmenu.shortcuts" )
        else:
            # No custom shortcuts or defaults available
            path = ""
            
        if not path == "":
            try:
                # Try loading shortcuts
                file = xbmcvfs.File( path )
                loaditems = eval( file.read() )
                file.close()
                
                listitems = []
                
                for item in loaditems:
                    path = sys.argv[0] + "?type=launch&path=" + urllib.quote( "RunScript(script.skinshortcuts,type=manage&group=" + item[0].replace(" ", "").lower() + ")" )
                    
                    listitem = xbmcgui.ListItem(label=__language__(32036) + item[0], label2="", iconImage="", thumbnailImage="")
                    listitem.setProperty('isPlayable', 'True')
                    
                    # Localize strings
                    if not item[0].find( "::SCRIPT::" ) == -1:
                        path = sys.argv[0] + "?type=launch&path=" + urllib.quote( "RunScript(script.skinshortcuts,type=manage&group=" + self.createNiceName( item[0][10:] ) + ")" )
                        listitem.setLabel( __language__(32036) + __language__(int( item[0][10:] ) ) )
                    elif not item[0].find( "::LOCAL::" ) == -1:
                        path = sys.argv[0] + "?type=launch&path=" + urllib.quote( "RunScript(script.skinshortcuts,type=manage&group=" + self.createNiceName( item[0][9:] ) + ")" )
                        listitem.setLabel( __language__(32036) + xbmc.getLocalizedString(int( item[0][9:] ) ) )
                        
                    xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=path, listitem=listitem)

            except:
                print_exc()
                log( "### ERROR could not load file %s" % path )
        
        # Add a link to reset all shortcuts
        path = sys.argv[0] + "?type=resetall"
        listitem = xbmcgui.ListItem(label=__language__(32037), label2="", iconImage="DefaultShortcut.png", thumbnailImage="DefaultShortcut.png")
        listitem.setProperty('isPlayable', 'True')
        xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=path, listitem=listitem)
        
        # Save the list
        xbmcplugin.endOfDirectory(handle=int(sys.argv[1]))
        
    def _reset_all_shortcuts( self ):
        log( "### Resetting all shortcuts" )
        dialog = xbmcgui.Dialog()
        
        # Ask the user if they're sure they want to do this
        if dialog.yesno(__language__(32037), __language__(32038)):
            # List all shortcuts
            files = xbmcvfs.listdir( __datapath__ )
            for file in files:
                try:
                    # Try deleting all shortcuts
                    if file:
                        file_path = os.path.join( __datapath__, file[0])
                        if xbmcvfs.exists( file_path ):
                            xbmcvfs.delete( file_path )
                except:
                    print_exc()
                    log( "### ERROR could not delete file %s" % file_path )
        
            # Update home window property (used to automatically refresh type=settings)
            xbmcgui.Window( 10000 ).setProperty( "skinshortcuts",strftime( "%Y%m%d%H%M%S",gmtime() ) )
            
            # Check for settings
            self.checkForSettings()   
            
            # Reset all window properties (so menus will be reloaded)
            self.reset_window_properties()
                
        # Tell XBMC not to try playing any media
        xbmcplugin.setResolvedUrl( handle=int( sys.argv[1]), succeeded=False, listitem=xbmcgui.ListItem() )
    

    # HELPER FUNCTIONS
    def checkVisibility ( self, item ):
        # Return whether mainmenu items should be displayed
        #if item == "movies":
        #    return xbmc.getCondVisibility("Library.HasContent(Movies)")
        #elif item == "tvshows":
        #    return xbmc.getCondVisibility("Library.HasContent(TVShows)")
        if item == "livetv":
            return xbmc.getCondVisibility("System.GetBool(pvrmanager.enabled)")
        elif item == "musicvideos":
            return xbmc.getCondVisibility("Library.HasContent(MusicVideos)")
        #elif item == "music":
        #    return xbmc.getCondVisibility("Library.HasContent(Music)")
        elif item == "weather":
            return xbmc.getCondVisibility("!IsEmpty(Weather.Plugin)")
        elif item == "dvd":
            return xbmc.getCondVisibility("System.HasMediaDVD")
        else:
            return True
            
    def createNiceName ( self, item ):
        # Translate certain localized strings into non-localized form for labelID
        if item == "10006":
            return "videos"
        if item == "342":
            return "movies"
        if item == "20343":
            return "tvshows"
        if item == "32022":
            return "livetv"
        if item == "10005":
            return "music"
        if item == "20389":
            return "musicvideos"
        if item == "10002":
            return "pictures"
        if item == "12600":
            return "weather"
        if item == "10001":
            return "programs"
        if item == "32032":
            return "dvd"
        if item == "10004":
            return "settings"
        else:
            return item
            
    def checkForSettings( self ):
        # Iterate through main menu, searching for a link to settings
        hasSettingsLink = False
        
        if xbmcvfs.exists( os.path.join( __datapath__ , "mainmenu.shortcuts" ) ):
            # User defined shortcuts
            mainmenuPath = os.path.join( __datapath__ , "mainmenu.shortcuts" )
        elif xbmcvfs.exists( os.path.join( __skinpath__ , "mainmenu.shortcuts" ) ):
            # Skin-provided defaults
            mainmenuPath = os.path.join( __skinpath__ , "mainmenu.shortcuts" )
        elif xbmcvfs.exists( os.path.join( __defaultpath__ , "mainmenu.shortcuts" ) ):
            # Script-provided defaults
            mainmenuPath = os.path.join( __defaultpath__ , "mainmenu.shortcuts" )
        else:
            # No custom shortcuts or defaults available
            mainmenuPath = ""
            
        if not mainmenuPath == "":
            try:
                # Try loading shortcuts
                loaditems = eval( file( mainmenuPath, "r" ).read() )
                
                for item in loaditems:
                    # Check if the path (item 4) is for settings
                    if urllib.unquote(item[4]) == "ActivateWindow(Settings)":
                        hasSettingsLink = True
                        break
                    
                    # Get labelID so we can check shortcuts for this menu item
                    groupName = item[0].replace(" ", "").lower()
                    
                    # Localize strings
                    if not item[0].find( "::SCRIPT::" ) == -1:
                        groupName = self.createNiceName( item[0][10:] )
                    elif not item[0].find( "::LOCAL::" ) == -1:
                        groupName = self.createNiceName( item[0][9:] )
                        
                    # Check if this item is actually being displayed
                    if self.checkVisibility( groupName ):
                        
                        # Get path of submenu shortcuts
                        if xbmcvfs.exists( os.path.join( __datapath__ , groupName + ".shortcuts" ) ):
                            # User defined shortcuts
                            submenuPath = os.path.join( __datapath__ , groupName + ".shortcuts" )
                        elif xbmcvfs.exists( os.path.join( __skinpath__ , groupName + ".shortcuts" ) ):
                            # Skin-provided defaults
                            submenuPath = os.path.join( __skinpath__ , groupName + ".shortcuts" )
                        elif xbmcvfs.exists( os.path.join( __defaultpath__ , groupName + ".shortcuts" ) ):
                            # Script-provided defaults
                            submenuPath = os.path.join( __defaultpath__ , groupName + ".shortcuts" )
                        else:
                            # No custom shortcuts or defaults available
                            submenuPath = ""
                            
                        if not submenuPath == "":
                            try:
                                # Try loading shortcuts
                                submenuitems = eval( file( submenuPath, "r" ).read() )
                                
                                for item in submenuitems:
                                    if urllib.unquote(item[4]) == "ActivateWindow(Settings)":
                                        hasSettingsLink = True
                                        break
                                    
                            except:
                                print_exc()
                                log( "### ERROR could not load file %s" % submenuPath )
                            
                    if hasSettingsLink == True:
                        break
            except:
                print_exc()
                log( "### ERROR could not load file %s" % mainmenuPath )
                
        if hasSettingsLink:
            log( " --- Skin has a link to settings" )
            # There's a settings link, delete our info file
            file_path = os.path.join( __datapath__, "nosettings.info")
            if xbmcvfs.exists( file_path ):
                xbmcvfs.delete( file_path )
            xbmcgui.Window( 10000 ).setProperty( "SettingsShortcut","True" )
        else:
            # There's no settings link, create an info file
            log( " --- Skin has no link to settings" )
            file_path = os.path.join( __datapath__, "nosettings.info")
            if not xbmcvfs.exists( file_path ):
                f = xbmcvfs.File( file_path, 'w' )
                f.write( "Meta-file to indicate there is no link to settings detected" )
                f.close()
            xbmcgui.Window( 10000 ).setProperty( "SettingsShortcut","False" )
            
    def reset_window_properties( self ):
        log( "Cleared skin overrides" )
        xbmcgui.Window( 10000 ).clearProperty( "skinshortcuts-overrides-skin" )
        
        log( "Cleared property for mainmenu" )
        xbmcgui.Window( 10000 ).clearProperty( "skinshortcuts-mainmenu" )
        listitems = self._get_shortcuts( "mainmenu" )
        for item in listitems:
            # Get labelID so we can check shortcuts for this menu item
            groupName = item[0].replace(" ", "").lower()
            
            # Localize strings
            if not item[0].find( "::SCRIPT::" ) == -1:
                groupName = self.createNiceName( item[0][10:] )
            elif not item[0].find( "::LOCAL::" ) == -1:
                groupName = self.createNiceName( item[0][9:] )        
                
            # Clear the property
            log( "Cleared property for " + groupName )
            xbmcgui.Window( 10000 ).clearProperty( "skinshortcuts-" + groupName )
            
if ( __name__ == "__main__" ):
    log('script version %s started' % __addonversion__)
    
    Main()
            
    log('script stopped')