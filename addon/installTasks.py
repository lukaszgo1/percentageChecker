# -*- coding: UTF-8 -*-

# Install tasks for Percentage checker add-on
#Copyright (C) 2019 Łukasz Golonka <lukasz.golonka@mailbox.org>
# Released under GPL 2


import addonHandler
import gui
import wx


addonHandler.initTranslation()

def onInstall():
	for addon in addonHandler.getAvailableAddons():
		if addon.name == "jump to line":
			gui.messageBox(
				# Translators: Content of the dialog informing about presence of old no longer needed add-on.
				_("Functionality of The jump to line add-on that you have installed is now included in the percentage checker. After pressing OK it would be removed."),
				# Translators: Title of the dialog
				_("Information"),
				wx.OK
			)
			addon.requestRemove()
