# Intention: a script that writes an XML that will contain the dictionary values and items that will be used as inputs into the 
# Forecast model and the Methane Model
# - Start date and date for electrciity data (NEMOSIS and other electricity markets)
# - Start date and date for gas data (AUS,USA, Europe and JKN)
# - Forecast horizon (simple input; include warning of extreme horizons max. 36 months)

import pandas as pd
import numpy as np
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, Any, List, Union

class ConfigUtils:
    @staticmethod
    def validate_date(date_str: str) -> Union[datetime, None]:
        """Validate and convert date string to datetime"""
        try:
            # First try to parse with pandas
            date = pd.to_datetime(date_str, errors="coerce")
            
            if date > datetime.now():
                print(f'Date cannot be greater than {datetime.now().strftime("%d-%m-%Y")}')
                return None
            return date
        except (ValueError, TypeError):
            print("Error: Date input is incorrect. Please enter a valid date in DD-MM-YYYY format.")
            return None

    @staticmethod
    def validate_integer(integer_input: int) -> Union[int,None]:
        """Validate and check inputs are integers"""
        min_value = 0
        try:
            value = int(integer_input)
            if value < min_value:
                print(f"Error: Please enter an integer greater than {min_value}")
                return None
            return value
        except ValueError:
            print("Error: Please enter an integer")
            return None
    
    @staticmethod 
    def validate_float(float_input: float) -> Union[float,None]:
        """Validate and check inputs are float"""
        min_value = 0
        try:
            value = float(float_input)
            if value < min_value:
                print(f"Error: Please enter a number greater than {min_value}")
                return None
            return value
        except ValueError:
            print("Error: Please enter a number")
            return None

    
    
    @staticmethod
    def parse_xml_config(xml_file: str) -> Dict[str, Dict[str, Any]]:
        """Convert XML configuration file to structured dictionary format"""
        # Parse XML to initial dictionary
        tree = ET.parse(xml_file)
        root = tree.getroot()
        
        def recursive_parse(element):
            result = {}
            for child in element:
                if len(child):
                    result[child.tag] = recursive_parse(child)
                else:
                    try:
                        value = float(child.text)
                        if value.is_integer():
                            value = int(value)
                    except (ValueError, TypeError):
                        value = child.text
                    result[child.tag] = value
            return result
        
        dict_input = {root.tag: recursive_parse(root)}
        
        # Extract and structure the configuration data
        plant_details = dict_input['ModelConfiguration']['Plant_Details']
        methane_pyrolysis = dict_input['ModelConfiguration']['Methane_Pyrolysis'] 
        hydrogen_graphite = dict_input['ModelConfiguration']['Hydrogen_Graphite_Market']
        
        date_range = {
            'start_date': dict_input['ModelConfiguration']['DateRange']['StartDate'],
            'end_date': dict_input['ModelConfiguration']['DateRange']['EndDate']
        }
        
        region_info = {
            'global_region': dict_input['ModelConfiguration']['Regions']['GlobalRegion'],
            'local_region': dict_input['ModelConfiguration']['Regions']['LocalRegion'] if 'LocalRegion' in dict_input['ModelConfiguration']['Regions'] else None,
            'NG_API': list(dict_input['ModelConfiguration']['NG_API'].values())[0] 
        }

        return {
            'plant_details': plant_details,
            'methane_pyrolysis': methane_pyrolysis,
            'hydrogen_graphite': hydrogen_graphite,
            'date_range': date_range,
            'region_info': region_info
        }


    @staticmethod
    def dict_to_xml(data: Dict[str, Any], filename: str) -> None:
        """Convert dictionary to XML and save to file"""
        root = ET.Element('ModelConfiguration')
        
        def add_elements(parent, data_dict):
            for key, value in data_dict.items():
                child = ET.SubElement(parent, key)
                if isinstance(value, dict):
                    add_elements(child, value)
                else:
                    child.text = str(value)
        
        add_elements(root, data)
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        tree.write(filename, encoding='utf-8', xml_declaration=True)




class model_setup:
    def __init__(self):
        self._check_run = False
        self._GlobalRegion = {'Global region':['AUS','USA','EUR','JKN']}
        self._NEMRegion = {'AUS region':['NSW1','QLD1','VIC1','SA1']}
        self._NG_API = {'USA':'NG=F','EUR':'TTF=F','JKN':'JKN=F'} 
        self.config = {}
        self._AUSregion = None
        self._GlblRegion = None

    
    def select_daterange(self) -> List[datetime]:
        """Get and validate date range from user input"""
        while True:
            # Get start date
            start_date = ConfigUtils.validate_date(
                input("Please select start date (DD-MM-YYYY): "))
            if not start_date:
                continue
            
            # Get end date
            end_date = ConfigUtils.validate_date(
                input("Please select end date (DD-MM-YYYY): "))
            if not end_date:
                continue
            
            # Check if start date is before end date
            if start_date > end_date:
                print("Start date must be before or equal to end date.")
                continue
            
            return [start_date, end_date]

    def select_Region(self):
        # Get list of global regions
        global_regions = self._GlobalRegion['Global region']
        
        while True:
            i = str(input(f"Please select from the global regions {global_regions}: ").upper())
            if i not in global_regions:
                print(f"Invalid selection. Please choose from: {global_regions}")
                continue
                
            self._GlblRegion = i
                    
            # If AUS is selected, prompt for specific region
            if i == 'AUS':
                aus_regions = self._NEMRegion['AUS region']
                while True:
                    j = str(input(f"Please select from the Australian regions {aus_regions}: ").upper())
                    if j not in aus_regions:
                        print(f"Invalid selection. Please choose from: {aus_regions}")
                        continue
                    
                    self._AUSregion = j
                    return {'global': i, 'local': j}
                    
            return {'global': i}

    def NEMOSIS_setup(self) -> Dict[str, Union[str, List[str]]]:
        """Setup NEMOSIS configuration"""
        return {
            'table': 'DISPATCHPRICE',
            'select_columns': ['REGIONID', 'RRP'],
            'column_filter': 'REGIONID',
            'region_filter': self._AUSregion
        }

    def Plant_config(self) -> Dict[str,Union[int,float]]:
        """Setup Plant configuration"""
        self._plant_size = None
        self._CAPEX = None
        self._OPEX = None
        self._PlantAvailability = None
        self._PlantEfficiency = None
        self._PlantLife = None

        Plant_config = {}

        while True:
            self._plant_size = ConfigUtils.validate_integer(input('Please enter the plant capacity in tonnes per year: '))
            self._CAPEX = ConfigUtils.validate_integer(input('Please enter the CAPEX in USD$m per year: '))
            self._OPEX = ConfigUtils.validate_integer(input('Please enter the OPEX in USD$m per year: '))  
            self._PlantAvailability = ConfigUtils.validate_float(input('Please enter the plant availability: '))
            self._PlantEfficiency = ConfigUtils.validate_float(input('Please enter the plant efficiency: '))
            self._PlantLife = ConfigUtils.validate_integer(input('Please enter the plant operating life in years: '))   
        
            if not self._plant_size or not self._CAPEX or not self._OPEX or not self._PlantAvailability or not self._PlantEfficiency or not self._PlantLife:
                print("Error: Please enter valid values for all fields")
                continue
            break
        
        self._Plant_data = {
                'Plant_Capacity': self._plant_size,  # in tonnes per year
                'CAPEX': self._CAPEX, # in USD$m per year
                'OPEX': self._OPEX,  # in USD$m per year
                'Plant_Efficiency': self._PlantEfficiency,  # Plant capacity to convert methane to H2
                'Availability': self._PlantAvailability,  # Plant downtime per year in %
                'Operating_Life_Years': self._PlantLife, # Operating life of plant
                'Days_Per_Year': 365,
                'Hours_Per_Day': 24,
                '_5_Min_Per_Hour': 12  # Using 5 min to allow for elec pricing         
        }

        self._Methane_Pyrolysis = {
            '_H2_mole': 2.016,
            '_C_mole': 12.011,
            '_CH4_mole': 16.042,
            '_Fe_per_tonne_Graphite': 0.2,
            '_MWh_per_tonne_Hydrogen': 9,
            '_GJ_per_tonne_Graphite': 86
        }

        # Hydrogen_Graphite_Market: H2 and C will be useful for DRI in Green Steel, C for anodes in Li-ion batteries
        self._Hydrogen_Graphite_Market = {
            'Mole_Fe2O3': 159.69,  # grams per mole
            'Mole_Fe': 55.84,  # grams per mole
            'Ratio_H2_mole_Fe2O3': 3,  # ratio of H2 mole required to reduced hematite to iron 
            'Ratio_Fe_mole_Fe2O3': 2,  # ratio of iron in hematite
            'Graphite_per_kWh': 0.45,  # ratio of graphite per kWh of Li-ion battery
            'kWh_per_EV': 300,  # size of Li-ion battery (kWh)
            'kWh_per_BESS': 1500  # size of Li-ion battery (kWh)
        }
        
        Plant_config['Plant_Details'] = self._Plant_data
        Plant_config['Methane_Pyrolysis'] = self._Methane_Pyrolysis
        Plant_config['Hydrogen_Graphite_Market'] = self._Hydrogen_Graphite_Market

        self._plant_config = Plant_config
        
        return self._plant_config
    
    def Natural_Gas_API(self) -> Dict[str, str]:
        if self._GlblRegion in self._NG_API:
            API = self._NG_API[self._GlblRegion]
            self._NG_API_config = API
            return {'NG_API': API}
        else:
            print(f"Warning: No Natural Gas API configured for region {self._GlblRegion}")
            return {'NG_API': None}
    
    
    def create_config_file(self, filename: str = 'model_config.xml') -> None:
        """Create and save complete model configuration
        
        Args:
            filename (str): Name of the output XML file. Defaults to 'model_config.xml'
            
        Raises:
            OSError: If there's an error writing the XML file
            ValueError: If required configuration data is missing
        """
        self._configfile = filename
        
        try:
            # Get date range once and store it
            date_range = self.select_daterange()
            
            # Validate both dates are not None
            if not date_range or None in date_range:
                raise ValueError("Invalid date range provided")
                
            # Ensure dates are datetime objects
            start_date, end_date = date_range
            if not isinstance(start_date, datetime) or not isinstance(end_date, datetime):
                raise ValueError("Invalid date objects in date range")
                
            # Build the configuration dictionary
            config_data = {
                'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'DateRange': {
                    'StartDate': start_date.strftime('%Y-%m-%d'),
                    'EndDate': end_date.strftime('%Y-%m-%d')
                }
            }
            
            # Get plant configuration first as it's required
            plant_config = self.Plant_config()
            if not plant_config:
                raise ValueError("Plant configuration is required")
            
            # Add plant configuration directly to config_data
            config_data.update(plant_config)  # This will add all plant config sections at the root level
            
            # Get region information
            region_info = self.select_Region()
            if not region_info:
                raise ValueError("Region selection is required")
                
            config_data['Regions'] = {
                'GlobalRegion': region_info['global']
            }

            config_data['NG_API'] = self.Natural_Gas_API()
            
            # Add local region and NEMOSIS config if applicable
            if 'local' in region_info:
                config_data['Regions']['LocalRegion'] = region_info['local']
                nemosis_config = self.NEMOSIS_setup()
                if nemosis_config:
                    config_data['NEMOSISConfig'] = nemosis_config
            
            # Save config to XML file
            try:
                ConfigUtils.dict_to_xml(config_data, filename)
            except Exception as e:
                raise OSError(f"Failed to save configuration to {filename}: {str(e)}")
            
            # Print formatted config data
            print(f"\nConfiguration saved to {filename}")
            print("\nConfiguration Contents:")
            print("----------------------")
            self._print_config(config_data)
            
        except (ValueError, OSError) as e:
            print(f"Error creating configuration: {str(e)}")
            raise

    def _print_config(self, d: Dict[str, Any], indent: int = 0) -> None:
        """Helper method to print configuration in a readable format
        
        Args:
            d: Dictionary to print
            indent: Current indentation level
        """
        for key, value in d.items():
            if isinstance(value, dict):
                print("  " * indent + f"{key}:")
                self._print_config(value, indent + 1)
            else:
                print("  " * indent + f"{key}: {value}")







