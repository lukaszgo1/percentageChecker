# -*- coding: UTF-8 -*-

# Percentage checker
# Copyright (C) 2012-2020 Original idea and code by Oriol Gómez <ogomez.s92@gmail.com>,
# improvements and maintenance by Łukasz Golonka <lukasz.golonka@mailbox.org>
# Released under GPL 2

import globalPluginHandler
import controlTypes
import api
import textInfos
import speech
from ui import message
import addonHandler
import scriptHandler
import wx
import gui
from globalCommands import SCRCAT_SYSTEMCARET
import os
import sys
import review
import core
addonHandler.initTranslation()


def _fixUpTI(ti):
	if ti.obj is None:
		# When the object for which the textInfo passed to the dialog loses focus
		# it's no longer valid therefore jumping, even after dialog closes, fails.
		# Since creating the TI from scratch is vastefull use this work around.
		ti.obj = api.getFocusObject()
	return ti


def _jumpToPos(posToJump, ti, movingUnit):
	ti = _fixUpTI(ti)
	try:
		speech.cancelSpeech()
		ti.move(movingUnit, int(posToJump), "start")
		ti.updateCaret()
		ti.expand(textInfos.UNIT_LINE)
		review.handleCaretMove(ti)
		speech.speakTextInfo(
			ti,
			unit=textInfos.UNIT_LINE,
			reason=getattr(controlTypes, "REASON_CARET", None) or controlTypes.OutputReason.CARET
		)
	except NotImplementedError:
		pass


def _jumpToPercent(posToJump, ti, movingUnit):
	ti = _fixUpTI(ti)
	return _jumpToPos(
		float(posToJump) * (float(len(ti.text)) - 1) / 100, ti, movingUnit
	)


def beepPercent(percent):
	import tones
	import config
	tones.beep(
		config.conf["presentation"]["progressBarUpdates"]["beepMinHZ"] * 2 ** (float(percent) / 25.0), 40
	)


class jumpToDialog(wx.Dialog):

	_instance = None

	def __new__(cls, *args, **kwargs):
		if cls._instance is None:
			return super(jumpToDialog, cls).__new__(cls, *args, **kwargs)
		return cls._instance

	def __init__(self, title, fieldLabel, fieldMin, fieldMax, fieldCurrent, ti, movingUnit, jumpFunc):
		if self.__class__._instance is not None:
			return
		self.__class__._instance = self
		super(jumpToDialog, self).__init__(parent=gui.mainFrame, title=title)
		self.ti = ti
		self.movingUnit = movingUnit
		self.jumpTo = jumpFunc
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		sHelper = gui.guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)
		self.entryField = sHelper.addLabeledControl(
			fieldLabel,
			gui.nvdaControls.SelectOnFocusSpinCtrl,
			min=fieldMin,
			max=fieldMax,
			initial=fieldCurrent,
			name=fieldLabel
		)
		sHelper.addDialogDismissButtons(self.CreateButtonSizer(wx.OK | wx.CANCEL))
		mainSizer.Add(sHelper.sizer, border=gui.guiHelper.BORDER_FOR_DIALOGS, flag=wx.ALL)
		self.Bind(wx.EVT_BUTTON, self.onOk, id=wx.ID_OK)
		self.Bind(wx.EVT_BUTTON, self.onClose, id=wx.ID_CANCEL)
		mainSizer.Fit(self)
		self.SetSizer(mainSizer)
		self.CentreOnScreen()
		self.entryField.SetFocus()

	def onOk(self, evt):
		core.callLater(
			100, self.jumpTo, posToJump=self.entryField.GetValue(), ti=self.ti, movingUnit=self.movingUnit
		)
		self.Destroy()
		self.__class__._instance = None

	def onClose(self, evt):
		self.Destroy()
		self.__class__._instance = None

	def __del__(self):
		self.__class__._instance = None

	@classmethod
	def run(cls, *args, **kwargs):
		gui.mainFrame.prePopup()
		d = cls(*args, **kwargs)
		if d:
			d.Show()
		gui.mainFrame.postPopup()


class GlobalPlugin(globalPluginHandler.GlobalPlugin):

	@scriptHandler.script(
		description=_(
			# Translators: Describes keyboard command which, depending of how many times is pressed,
			# either reports current percentage in speech
			# or displays a dialog allowing to jump to the particular percentage in the text.
			"Press this command once to have percentage in the text or on the list reported in speech."
			" Press it twice to display a dialog"
			" allowing you to jump to the given percentage in the currently focused text field"
		),
		gesture="kb:NVDA+shift+p",
		category=SCRCAT_SYSTEMCARET,
	)
	def script_reportOrJumpTo_speech(self, gesture):
		if scriptHandler.getLastScriptRepeatCount() <= 1:
			self.reportOrJumpTo(showJumpToDialog=bool(scriptHandler.getLastScriptRepeatCount() == 1))
		return

	@scriptHandler.script(
		description=_(
			# Translators: Describes keyboard command which, depending of how many times is pressed,
			# either reports current percentage as a beep
			# or displays a dialog allowing to jump to the particular percentage in the text.
			"Press this command once to have percentage in the text or on the list reported as a beep."
			" Press it twice to display a dialog"
			" allowing you to jump to the given percentage in the currently focused text field"
		),
		gesture="kb:NVDA+Alt+p",
		category=SCRCAT_SYSTEMCARET,
	)
	def script_reportOrJumpTo_beep(self, gesture):
		if scriptHandler.getLastScriptRepeatCount() <= 1:
			self.reportOrJumpTo(showJumpToDialog=bool(scriptHandler.getLastScriptRepeatCount() == 1))
		return

	@scriptHandler.script(
		description=_(
			# Translators: Describes keyboard command which displays a dialog
			# 		allowing to jump to the given line number in the text.
			"displays a dialog allowing you to jump to the given line number in the currently focused text field"
		),
		gesture="kb:NVDA+shift+j",
		category=SCRCAT_SYSTEMCARET,
	)
	def script_jumpToLine(self, gesture):
		if not hasattr(textInfos, "TextInfoEndpoint"):
			# Before NVDA 2021.1 collecting all lines from NVD'As edit controls causes a crash
			focusedObj = api.getFocusObject()
			if(
				focusedObj.role == controlTypes.ROLE_EDITABLETEXT
				and getattr(focusedObj, "processID", None) == os.getpid()
			):
				# Jumping to line in NVDA's own edit fields causes a crash, disable the script.
				# Translators: Message informing that the given script is not  supported in the focused control.
				message(_("Not supported here."))
				return
		try:
			current, total = self._prepare()
		except RuntimeError:
			return
		lineCount = len(tuple(total.getTextInChunks(textInfos.UNIT_LINE)))
		fullText = total.copy()
		total.setEndPoint(current, "endToStart")
		lineCountBeforeCaret = len(tuple(total.getTextInChunks(textInfos.UNIT_LINE)))
		jumpToDialog.run(
			# Translators: Title of the dialog.
			title=_("Jump to line"),
			# Translators: A message in the dialog allowing to jump to the given line number.
			fieldLabel=_("Enter line number (from 1 to {})").format(lineCount),
			fieldMin=1,
			fieldMax=lineCount,
			fieldCurrent=lineCountBeforeCaret,
			ti=fullText,
			movingUnit=textInfos.UNIT_LINE,
			jumpFunc=_jumpToPos
		)
		def callback(result):
			if result == wx.ID_OK:
				lineToJumpTo = jumpToLineDialog.GetValue()
				if not (lineToJumpTo.isdigit() and 1 <= int(lineToJumpTo) <= lineCount):
					wx.CallAfter(
						gui.messageBox,
						# Translators: Shown when user enters wrong value in the jump to line dialog.
						_("Wrong value."),
						# Translators: Title of the error dialog
						_("Error"), 
						wx.OK|wx.ICON_ERROR
					)
					return
				wx.CallLater(100, self._jumpTo, posToJump = (int(lineToJumpTo)-1), info = fullText, movingUnit = textInfos.UNIT_LINE)
		return

	def reportOrJumpTo(self, showJumpToDialog):
		obj=api.getFocusObject()
		callerName = sys._getframe(1).f_code.co_name
		if obj.role == controlTypes.ROLE_LISTITEM:
			if showJumpToDialog:
				# Jumping when focused on a list is not supported.
				return
			if hasattr(obj, 'positionInfo') and obj.positionInfo:
				# Using positionInfo is very fast, so prefer this.
				currPos = float(obj.positionInfo['indexInGroup'])
				totalCount = float(obj.positionInfo['similarItemsInGroup'])
			elif hasattr(obj, "IAccessibleChildID") and obj.IAccessibleChildID >0 and obj.parent and obj.parent.childCount:
				currPos = float(obj.IAccessibleChildID)
				totalCount = float(obj.parent.childCount)
			else:
				# This was present in the original code. Even though it is slow as hell it might be needed in some obscure cases when positionInfo is not implemented.
				objList = obj.parent.children
				# Get rit of all non-listItems objects such as headers, scrollbars etc.
				if objList[-1].role in (controlTypes.ROLE_HEADER, controlTypes.ROLE_LIST):
					objList.remove(objList[-1])
				for  listItem in objList:
					if listItem.role == controlTypes.ROLE_LISTITEM:
						break
					else:
						objList.remove(listItem)
				totalCount = float(len(objList))
				currPos = float(objList.index(obj))
				if currPos == 0:
					currPos += 1
			posInPercents = int(currPos / totalCount * 100)
			if callerName == 'script_reportOrJumpTo_speech':
				# Translators: Reported when user asks about position in a list.
				# The full message is as follows:
				# 25 percent, item 1 of 4
				message(_("{0} percent, item {1} of {2}").format(posInPercents, int(currPos), int(totalCount)))
			if callerName =='script_reportOrJumpTo_beep':
				beepPercent(posInPercents)
			return
		try:
			current, total = self._prepare()
		except RuntimeError:
			return
		totalCharsCount = float(len(total.text))
		totalWordsCount = len(total.text.split())
		totalToPass = total.copy()
		total.setEndPoint(current, "endToStart")
		wordCountBeforeCaret = len(total.text.split())
		charsCountBeforeCaret = float(len(total.text))
		posInPercents = int(charsCountBeforeCaret / totalCharsCount * 100)
		if showJumpToDialog:
			jumpToDialog.run(
				# Translators: Title of the dialog.
				title=_("Jump to percent"),
				# Translators: A message in the dialog allowing to jump to the given percentage.
				fieldLabel=_("Enter a percentage to jump to"),
				fieldMin=0,
				fieldMax=100,
				fieldCurrent=posInPercents,
				ti=totalToPass,
				movingUnit=textInfos.UNIT_CHARACTER,
				jumpFunc=_jumpToPercent
			)
			def callback(result):
				if result == wx.ID_OK:
					percentToJumpTo = jumpToPercentDialog.GetValue()
					if not (percentToJumpTo.isdigit() and 0 <= int(percentToJumpTo) <= 100):
						wx.CallAfter(
							gui.messageBox,
							# Translators: Shown when user enters wrong value in the dialog.
							_("Wrong value. You can enter a percentage between 0 and 100."),
							# Translators: Title of the error dialog
							_("Error"), 
							wx.OK|wx.ICON_ERROR
						)
						return
					wx.CallLater(100, self._jumpTo, posToJump=float(percentToJumpTo)*(totalCharsCount-1)/100, info = total, movingUnit = textInfos.UNIT_CHARACTER)
			return
		if callerName == 'script_reportOrJumpTo_speech':
			# Translators: Presented to the user when command to report percentage in the current text is pressed.
			# Full message is as follows:
			# 80 percent word 486 of 580
			message(_("{0} percent word {2} of {1}").format(posInPercents, totalWordsCount, wordCountBeforeCaret))
		if callerName == 'script_reportOrJumpTo_beep':
			beepPercent(posInPercents)
		return

	@staticmethod
	def _prepare():
		obj = api.getFocusObject()
		treeInterceptor = obj.treeInterceptor
		if hasattr(treeInterceptor, 'TextInfo') and not treeInterceptor.passThrough:
			obj = treeInterceptor
		try:
			total = obj.makeTextInfo(textInfos.POSITION_ALL)
		except (NotImplementedError, RuntimeError):
			raise RuntimeError("Invalid object")
		try:
			current = obj.makeTextInfo(textInfos.POSITION_CARET)
		except (NotImplementedError, RuntimeError):
			# Translators: Announced when there is no caret in the currently focused control.
			message(_("Caret not found"))
			raise RuntimeError("Cannot work with object with no caret")
		if total.text == '':
			# Translators: Reported when the field with caret is empty
			message(_("No text"))
			raise RuntimeError("Cannot work with empty field")
		return current, total
