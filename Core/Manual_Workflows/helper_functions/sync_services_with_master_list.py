"""
This script updates all of the service descriptions as they have been provided
in the Google doc here: 
https://docs.google.com/spreadsheets/d/122rzEC4brsSe_P7iQCyNe0pj2j4t14t17coIyd6IBcM

The document must be downloaded as a CSV, and then the path to that CSV passed
in as the first command-line argument to this script.

Usage: sync_services_with_master_list.py path/to/services_download.csv
"""
import sys
from pathlib import Path
import csv
import ruamel.yaml

yaml = ruamel.yaml.YAML()

THIS_DIR = Path(__file__).parent
CORE_DIR = THIS_DIR.parent.parent
SERVICES_ROOT = CORE_DIR / 'LAMBDA' / 'viz_functions' / 'viz_publish_service' / 'services'

def gather_service_yamls():
    service_to_yaml = {}
    for root, dirs, files in SERVICES_ROOT.walk():
        for f in files:
            if f.endswith('.yml'):
                yaml_fpath = Path(root) / f
                service_to_yaml[yaml_fpath.name.split('.')[0]] = yaml_fpath
    
    return service_to_yaml

def main(services_csv_fpath):
    yaml_fpaths = gather_service_yamls()
    with open(services_csv_fpath) as f:
        csv_reader = csv.reader(f)
        for i, row in enumerate(csv_reader):
            if i == 0: continue
            if not row[0].strip(): continue
            service_path, is_public, current_live, next_live, support, service_type, ogc_wms_wfs, in_monitor, acceptable_delay, new_description, current_description, comments = row
            service_name = service_path.split('/')[1].split('(')[0].strip()
            if service_name in yaml_fpaths:
                print(f"Updating {service_name}")
                yaml_fpath = yaml_fpaths[service_name]
                yaml_obj = yaml.load(yaml_fpath.read_text())
                if new_description and "Service Description" in new_description:
                    new_description = new_description.split('Service Description:')[1].strip()
                    yaml_obj['description'] = new_description
                else:
                    print(f"!!!Description not found for {service_name}!!!")
                yaml_obj['public_service'] = is_public == "Yes"
                yaml_obj['feature_service'] = 'Feature' in service_type
                with open(yaml_fpath, 'w') as outfile:
                    yaml.dump(yaml_obj, outfile)
            else:
                print(f"!!!!YAML not found for {service_name}!!!!")
if __name__ == "__main__":
    main(sys.argv[1])
    print("DONE")
