"""
YamlLoader: A class to load YAML configurations and validate them against a schema.
Imports:
- yaml: A library for working with YAML files. Used for loading YAML data.
- Validator from cerberus: A library for data validation. Used for validating configurations against a schema.
- logging: Logging facility for Python.
"""
import os
import logging
import yaml
from cerberus import Validator

# Configure logging
# logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class YamlLoader:
    """
    Represents a YAML configuration file loader, where each item in the list becomes an instance of YamlConfigItem.
    This class provides functionality to load YAML configurations from a file, validate them against a schema,
    and retrieve configurations and instances of YamlConfigItem.
    Args:
        file_path (str): The path to the YAML file containing configurations.
    Attributes:
        __schema_file (str): The path to the YAML schema file.
        __schema_data (dict): The schema data loaded from the schema file.
        __file_path (str): The path to the YAML configuration file.
        config_data (list): The YAML configuration data loaded from the file.
        __instances (list): A list of instances of YamlConfigItem representing configurations.
    Methods:
        __init__(file_path): Initializes the YamlLoader with the file path to the YAML configurations.
        __create_instance(data): Creates an instance of YamlConfigItem from the given data.
        __validate_yaml(data): Validates configurations against the schema.
        get_instances(): Gets all valid instances of YamlConfigItem.
        get_configurations(): Returns all configurations.
        get_configuration(index): Returns a configuration by index.
        __load_yaml(file_path): Loads YAML data from a file.

    """
    def __init__(self, file_path):
        """
        Initializes the YamlLoader with the file path to the YAML configurations.
        Args:
        - file_path (str): The path to the YAML file containing configurations.
        """
        self.__schema_file = "search_schema.yaml"
        self.__schema_data = self.__load_yaml(self.__schema_file)
        self.__file_path = file_path
        self.config_data = self.__load_yaml(self.__file_path)

        self.__instances = [self.__create_instance(i, item) \
                            for i, item in enumerate(self.config_data, start=1)]

        valids = self.get_len_valid_configs()
        configs = self.get_len_loaded_configs()
        logger.info("A total of %s out of %s configurations were successfully imported.",
                    valids, configs)

    def get_len_valid_configs(self):
        """
        Gets the number of validated configurations from YAML file.
        Returns:
            int: A number indication how many configurations are valid inside the file.
        """
        return len(list(filter(None, self.__instances)))

    def get_len_loaded_configs(self):
        """
        Gets the total number of loaded configurations from YAML file.
        Returns:
            int: A number indication how many configurations are there inside the file.
        """
        return len(self.__instances)


    def __create_instance(self, index, data):
        """
        Creates an instance of YamlConfigItem from the given data.
        Args:
        - data (dict): The data representing a single configuration.
        Returns:
        - YamlConfigItem: An instance representing the configuration.
        """
        #return YamlConfigItem(self.__validate_yaml(data))
        validation_results = self.__validate_yaml(data)
        for result in validation_results:
            logger.info("Configuration #%s is valid: %s" , index, result['is_valid'])
            if result['is_valid']:
                return YamlConfigItem(result['yaml_config'])
            else:
                logger.info("Errors: %s" , result['errors'])


    def __validate_yaml(self, data):
        """
        Validates configurations against the schema.
        Returns:
        - list of dict: A list of validation results for each configuration.
          Each validation result contains the configuration number, validation status,
          and validation errors.
        Usage:
            validation_results = loader.validate_yaml()
            for result in validation_results:
                print(f"Configuration '{result['config_number']}' is valid:", result['is_valid'])
                if not result['is_valid']:
                    print("Errors:")
                    print(result['errors'])
        """
        val_results = []
        val = Validator(self.__schema_data)
        normalized_data = val.normalized(data, self.__schema_data)
        #for index, yaml_config in enumerate(self.config_data, start=1):
        is_valid = val.validate(normalized_data, self.__schema_data)
        val_results.append({
            'yaml_config': normalized_data,
            'is_valid': is_valid,
            'errors': val.errors
        })

        return val_results

    def get_instances(self):
        """
        Gets all valid instances of YamlConfigItem.
        Returns:
            list: A list containing all valid instances of YamlConfigItem.
        """
        instances = list(filter(None, self.__instances))
        return instances

    def get_configurations(self):
        """
        Returns all configurations.
        Returns:
        - list of dict: All configurations loaded from the YAML file.
        """
        return self.config_data

    def get_configuration(self, index):
        """
        Returns a configuration by index.
        Args:
        - index (int): The index of the configuration to retrieve.
        Returns:
        - dict: The configuration at the specified index.
        Raises:
        - IndexError: If the index is out of range.
        """
        if index < 0 or index >= len(self.config_data):
            raise IndexError("Invalid configuration index.")
        return self.config_data[index]

    def __load_yaml(self, file_path):
        """
        Loads YAML data from a file.
        Args:
        - file_path (str): The path to the YAML file.
        Returns:
        - list: The YAML data loaded from the file.
        """
        if not os.path.isfile(file_path):
            logger.error("YAML file not found at path: %s", file_path)
            if file_path == self.__schema_file:
                raise FileNotFoundError("An important YAML schema file was \
                                        not found at path. Aborted")
            return None

        try:
            with open(file_path, 'r', encoding='utf8') as file:
                logger.info('YAML file successfully loaded: %s', file_path)
                return yaml.safe_load(file)
        except FileNotFoundError:
            logger.error("YAML file not found at path: %s", file_path)
            raise
        except yaml.YAMLError as e:
            logger.error("Error occurred while parsing YAML file at path %s: %s",
                         file_path, str(e))
        except Exception as e:
            logger.error("An unexpected error occurred while loading YAML file at path %s: %s",
                         file_path, str(e))
        return None


class YamlConfigItem:
    """
    Represents a single configuration item in the YAML configuration file.
    """
    def __init__(self, data):
        """
        Initializes the YamlConfigItem with the configuration data.
        Args:
        - data (dict): The data representing a single configuration.
        """
        self.data = data
        # self.errors =


    def get_value_by_key(self, key):
        """
        Gets the value associated with the given key in the configuration.
        Args:
        - key (str): The key to search for.
        Returns:
        - str or None: The value associated with the key if found, otherwise None.
        """
        return self._get_value_by_key_recursive(self.data, key)

    def _get_value_by_key_recursive(self, data, key):
        """
        Helper method to get the value associated with the given key in the configuration.
        Args:
        - data (dict or list): The nested dictionary or list to search within.
        - key (str): The key to search for.
        Returns:
        - str or None: The value associated with the key if found, otherwise None.
        """
        if isinstance(data, dict):
            for k, v in data.items():
                if k == key:
                    return v
                elif isinstance(v, (dict, list)):
                    result = self._get_value_by_key_recursive(v, key)
                    if result is not None:
                        return result
        elif isinstance(data, list):
            for item in data:
                result = self._get_value_by_key_recursive(item, key)
                if result is not None:
                    return result
        return None

## Example usage:
#yaml_config = YamlLoader("search_config.yaml")
#for index, instance in enumerate(yaml_config.get_instances(), start=1):
#    service_opt = instance.get_value_by_key('service_opt')
#    #print("Value for key 'service_opt': ", service_opt)
#    print('Config #%s:' % index)
#    print("Tema: %s, subtema: %s, motivo: %s" % (service_opt.get("tema", ''),
#          service_opt.get("subtema", ''), service_opt.get("motivo", '')))
#    location_opt = instance.get_value_by_key('location_opt')
#    print("Distrito: %s, localidade: %s, local_atendimento: %s" % (location_opt.get("distrito", ''),
#          location_opt.get("localidade", ''), location_opt.get("local_atendimento", '')))
#    print(instance.get_value_by_key('title'))