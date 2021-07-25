import wx

import core
import gui


class JumpToDialog(wx.Dialog):

	_instance = None

	def __new__(cls, *args, **kwargs):
		if cls._instance is None:
			return super(JumpToDialog, cls).__new__(cls, *args, **kwargs)
		return cls._instance

	def __init__(self, title, fieldLabel, fieldMin, fieldMax, fieldCurrent, ti, movingUnit, jumpFunc):
		if self.__class__._instance is not None:
			return
		self.__class__._instance = self
		super(JumpToDialog, self).__init__(parent=gui.mainFrame, title=title)
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
