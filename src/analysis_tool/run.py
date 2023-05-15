from initialize import prepare_csv

import pandas as pd
import keyring

data_dir = keyring.get_password("msp", "vmt_reduction_dir")
df = pd.read_csv(data_dir + "/data_processed/feasible_shifts.csv")

x = prepare_csv(df, data_dir)