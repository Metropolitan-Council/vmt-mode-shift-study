from initialize import prepare_csv

import pandas as pd
import keyring
from PyQt5 import QtCore, QtWidgets
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
import sys
import steps as st

data_dir = keyring.get_password("msp", "vmt_reduction_dir")
df = pd.read_csv(data_dir + "/data_processed/feasible_shifts.csv")

x = prepare_csv(df, data_dir)

# class MplCanvas(FigureCanvasQTAgg):

#     def __init__(self, parent=None, width=5, height=4, dpi=100):
#         fig = Figure(figsize=(width, height), dpi=dpi)
#         self.axes = fig.add_subplot(111)
#         super(MplCanvas, self).__init__(fig)


# class MainWindow(QtWidgets.QMainWindow):

#     def __init__(self, *args, **kwargs):
#         super(MainWindow, self).__init__(*args, **kwargs)

#         # Create the maptlotlib FigureCanvas object,
#         # which defines a single set of axes as self.axes.
#         sc = MplCanvas(self, width=5, height=4, dpi=100)
#         sc.axes.plot([0,1,2,3,4], [10,1,20,3,40])
#         self.setCentralWidget(sc)

#         self.show()

# df = pd.read_csv("data/tbi_full.csv")
# temp = st.feasible_steps.WalkDistanceStep(df)