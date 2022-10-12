
import sys
import argparse

# change path to source code as needed
sys.path.append("../../vmt-mode-shift-study/src")

import preprocess_tbi

if __name__ == '__main__':
    """
    Main script to run for VMT mode shift study. 
    
    Usage: python run_all.py -d [DATA_DIR] -c [CONFIG_DIR] -o [OUTPUT_DIR]
    
    IMPORTANT: No personally identifiable inforomation (including any point locations)
    should be uploaded to github!  Run this in a separate folder and don't check in data. 
    
    """

    # parse required arguments
    parser = argparse.ArgumentParser()
    
    parser.add_argument("-d", "--data_dir", type=str, required=True,
        help="path to data directory ")
        
    parser.add_argument("-c", "--config_dir", type=str, default="config",
        help="path to configuration data directory (default: config)")
    
    parser.add_argument("-o", "--output_dir", type=str, default="output",
        help="path to output directory (default: output)")
    
    args = parser.parse_args()

    # do stuff here...
    preprocess_tbi.read_and_clean_data(args.data_dir, args.config_dir, args.output_dir)
    
    print("All done!")

