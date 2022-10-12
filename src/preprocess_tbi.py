
import pandas as pd

def read_and_clean_data(data_dir, config_dir, output_dir):
    """
    Main method to process and clean Travel Behavior Inventory (TBI) data. 
    
    This does a number of things, including...
    
    (Currenlty it is a placeholder that just reads a data file to test that 
    it works.)
    """

    df = pd.read_csv(data_dir + "\household.csv")
    print(df.describe())
