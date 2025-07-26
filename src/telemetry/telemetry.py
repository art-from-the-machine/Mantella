import os
import logging
import threading
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor


@dataclass
class TelemetryContext:
    # Application metadata
    application_name: str = "mantella"
    application_version: str = ""
    game_type: str = ""
    mod_path: str = ""
    telemetry_enabled: bool = False
    
    # User context
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    
    # Runtime context
    start_time: datetime = field(default_factory=datetime.now)
    
    # Custom attributes that can be added dynamically
    custom_attributes: Dict[str, Any] = field(default_factory=dict)
    
    def to_resource_attributes(self) -> Dict[str, str]:
        attributes = {
            "service.name": self.application_name,
            "service.version": self.application_version,
            "game.type": str(self.game_type),
        }
        
        if self.user_id:
            attributes["user.id"] = self.user_id
        if self.session_id:
            attributes["session.id"] = self.session_id
            
        return attributes
    
    def add_custom_attribute(self, key: str, value: Any):
        """Add a custom attribute to the context."""
        self.custom_attributes[key] = value
    
    def get_all_attributes(self) -> Dict[str, Any]:
        """Get all attributes including custom ones."""
        base_attrs = self.to_resource_attributes()
        base_attrs.update(self.custom_attributes)
        return base_attrs


class TelemetryManager:
    # Singleton telemetry manager that provides global telemetry context.
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self._context = TelemetryContext()
            self._tracer_provider = None
            self._tracer = None
            self._is_initialized = False
    
    @property
    def context(self) -> TelemetryContext:
        return self._context
    
    @property
    def tracer(self):
        if not self._is_initialized:
            raise RuntimeError("TelemetryManager not initialized. Call initialize() first.")
        return self._tracer
    
    def initialize(self, 
                   config, 
                   version: str,
                   enable_telemetry: bool) -> None:
        if self._is_initialized:
            logging.warning("TelemetryManager already initialized")
            return
        
        # Update context with config data if available
        if config:
            self._context.application_version = version
            self._context.game_type = getattr(config, 'game', 'skyrim')
            self._context.mod_path = getattr(config, 'mod_path', '')
        
        if not enable_telemetry:
            logging.info("Telemetry disabled")
            self._is_initialized = True
            return        
        
        try:
            self._setup_opentelemetry(config.telemetry_otlp_endpoint, config.telemetry_protocol)
            self._is_initialized = True
            self._context.telemetry_enabled = True
            logging.info("Telemetry system initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize telemetry: {e}")
            self._is_initialized = True  # Mark as initialized to prevent retries
    
    def _setup_opentelemetry(self, endpoint: str, protocol: str):
        # Header will contain the telemetry API key if using a SaaS provider
        headers_str = os.getenv("OTEL_EXPORTER_OTLP_HEADERS", "")
        
        # Parse headers
        headers = {}
        if headers_str:
            for header in headers_str.split(","):
                if "=" in header:
                    key, value = header.split("=", 1)
                    headers[key.strip()] = value.strip()
        
        # Format headers for HTTP
        if headers:
            formatted_headers = {}
            for key, value in headers.items():
                formatted_key = key.title().replace('_', '-')
                formatted_headers[formatted_key] = value
            headers = formatted_headers
        
        # Ensure endpoint has correct path
        if not endpoint.endswith("/v1/traces"):
            endpoint = endpoint.rstrip("/") + "/v1/traces"
        
        # Create resource with context attributes
        resource = Resource.create(self._context.to_resource_attributes())
        
        # Create TracerProvider
        self._tracer_provider = TracerProvider(resource=resource)
        
        if protocol == "http/protobuf":
            if not endpoint.endswith("/v1/traces"):
                endpoint = endpoint.rstrip("/") + "/v1/traces"
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            otlp_exporter = OTLPSpanExporter(
                endpoint=endpoint,
                headers=headers if headers else None
            )
        elif protocol == "grpc":
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            otlp_exporter = OTLPSpanExporter(
                endpoint=endpoint,
                headers=headers if headers else None
            )
        else:
            raise ValueError(f"Unsupported telemetry protocol: {protocol}")


        # Add BatchSpanProcessor
        self._tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        
        # Set as global default
        trace.set_tracer_provider(self._tracer_provider)
        
        # Instrument common libraries
        RequestsInstrumentor().instrument()
        LoggingInstrumentor().instrument()
        
        # Create tracer
        self._tracer = trace.get_tracer(self._context.application_name)
        
        logging.info(f"Telemetry configured with endpoint: {endpoint}")
        logging.info(f"Resource attributes: {self._context.to_resource_attributes()}")
    
    def create_span(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        # Create a span with global context attributes.
        if not self._is_initialized or not self._context.telemetry_enabled:
            return _DummySpan()
        
        span_attributes = self._context.get_all_attributes().copy()
        if attributes:
            span_attributes.update(attributes)
        
        return self._tracer.start_as_current_span(name, attributes=span_attributes)
    
    def add_global_attribute(self, key: str, value: Any):
        # Add an attribute that will be included in all future spans.
        self._context.add_custom_attribute(key, value)
    
    def set_user_id(self, user_id: str):
        # Set the user ID for all future telemetry.
        self._context.user_id = user_id
    
    def set_session_id(self, session_id: str):
        # Set the session ID for all future telemetry.
        self._context.session_id = session_id
    
    def get_uptime_seconds(self) -> float:
        # Get application uptime in seconds.
        return (datetime.now() - self._context.start_time).total_seconds()


class _DummySpan:
    # Dummy span for when telemetry is disabled.
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
    
    def set_attribute(self, key: str, value: Any):
        pass
    
    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        pass
    
    def record_exception(self, exception: Exception):
        pass


# Global instance
telemetry_manager = TelemetryManager()

# Convenience functions

def get_telemetry_manager() -> TelemetryManager:
    """Get the global telemetry manager instance."""
    return telemetry_manager


def create_span(name: str, attributes: Optional[Dict[str, Any]] = None):
    """Convenience function to create a span with global context."""
    return telemetry_manager.create_span(name, attributes)


def create_span_with_parent(name: str, parent_context, attributes: Optional[Dict[str, Any]] = None):
    """Create a span with a specific parent context (useful for cross-thread operations)."""
    if not telemetry_manager._is_initialized or not telemetry_manager._context.telemetry_enabled:
        return _DummySpan()
    
    span_attributes = telemetry_manager._context.get_all_attributes().copy()
    if attributes:
        span_attributes.update(attributes)
    
    from opentelemetry import context as otel_context
    from opentelemetry import trace as otel_trace
    
    if hasattr(parent_context, 'span_id'):  # It's a SpanContext
        ctx = otel_context.set_span_context(otel_context.get_current(), parent_context)
    else:
        ctx = parent_context
    
    return telemetry_manager._tracer.start_as_current_span(name, context=ctx, attributes=span_attributes)


def add_global_attribute(key: str, value: Any):
    """Convenience function to add global attributes."""
    telemetry_manager.add_global_attribute(key, value)
