from src.config.types.config_value import ConfigValue
from src.config.types.config_value_bool import ConfigValueBool
from src.config.types.config_value_string import ConfigValueString


class TelemetryDefinitions:
    #Base
    @staticmethod
    def get_enable_telemetry_config_value() -> ConfigValue:
        return ConfigValueBool("enable_telemetry","","Enable open telemetry for tracing",False)

    @staticmethod
    def get_telemetry_otlp_endpoint_config_value() -> ConfigValue:
        return ConfigValueString("telemetry_otlp_endpoint","","Open Telemetry endpoint","")
    
    @staticmethod
    def get_telemetry_protocol_config_value() -> ConfigValue:
        return ConfigValueString("telemetry_protocol","","Open Telemetry protocol (can be 'http/protobuf' or 'grpc')","http/protobuf")