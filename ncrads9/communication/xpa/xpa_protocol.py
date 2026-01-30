# NCRADS9 - XPA Protocol Implementation
# Copyright (C) 2026 Yogesh Wadadekar
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
XPA protocol implementation for DS9 compatibility.

Handles parsing and formatting of XPA protocol messages for communication
with external tools like xpaget, xpaset, and xpainfo.

Author: Yogesh Wadadekar
"""

import re
import logging
from typing import Any, Dict, List, Optional, Tuple, Union
from enum import Enum
from dataclasses import dataclass


class XPAMessageType(Enum):
    """XPA message types."""
    GET = "xpaget"
    SET = "xpaset"
    INFO = "xpainfo"
    ACCESS = "xpaaccess"


@dataclass
class XPAMessage:
    """Represents an XPA protocol message.
    
    Attributes:
        msg_type: The type of XPA message.
        target: The target access point name.
        command: The command to execute.
        params: Additional parameters.
        data: Binary or text data payload.
    """
    msg_type: XPAMessageType
    target: str
    command: str
    params: Dict[str, Any]
    data: Optional[bytes] = None


class XPAProtocol:
    """XPA protocol parser and formatter.
    
    This class handles the low-level protocol details for XPA communication,
    including message parsing, validation, and response formatting.
    """
    
    ENCODING: str = "utf-8"
    HEADER_TERMINATOR: bytes = b"\n"
    MESSAGE_TERMINATOR: bytes = b"\n\n"
    
    def __init__(self) -> None:
        """Initialize the XPA protocol handler."""
        self._logger: logging.Logger = logging.getLogger(__name__)
        
    def parse_request(self, data: bytes) -> Dict[str, Any]:
        """Parse an XPA request from raw bytes.
        
        Args:
            data: Raw bytes received from the client.
            
        Returns:
            Parsed request dictionary with command and parameters.
        """
        try:
            text = data.decode(self.ENCODING).strip()
            return self._parse_text_request(text)
        except UnicodeDecodeError as e:
            self._logger.error(f"Failed to decode XPA request: {e}")
            return {"command": "", "params": {}, "error": "decode_error"}
            
    def _parse_text_request(self, text: str) -> Dict[str, Any]:
        """Parse a text XPA request.
        
        Args:
            text: The request text to parse.
            
        Returns:
            Parsed request dictionary.
        """
        parts = text.split(None, 1)
        
        if not parts:
            return {"command": "", "params": {}}
            
        command = parts[0].lower()
        param_str = parts[1] if len(parts) > 1 else ""
        
        params = self._parse_params(param_str)
        
        return {
            "command": command,
            "params": params,
            "raw": text,
        }
        
    def _parse_params(self, param_str: str) -> Dict[str, Any]:
        """Parse parameter string into dictionary.
        
        Args:
            param_str: The parameter string to parse.
            
        Returns:
            Dictionary of parsed parameters.
        """
        params: Dict[str, Any] = {}
        
        if not param_str:
            return params
            
        # Handle key=value pairs
        kv_pattern = re.compile(r'(\w+)=("[^"]*"|[^\s]+)')
        matches = kv_pattern.findall(param_str)
        
        for key, value in matches:
            # Remove quotes if present
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            params[key] = self._convert_value(value)
            
        # Handle positional arguments
        remaining = kv_pattern.sub("", param_str).strip()
        if remaining:
            positional = remaining.split()
            if positional:
                if len(positional) == 1:
                    params["value"] = self._convert_value(positional[0])
                else:
                    params["args"] = [self._convert_value(p) for p in positional]
                    
        return params
        
    def _convert_value(self, value: str) -> Union[str, int, float, bool]:
        """Convert string value to appropriate type.
        
        Args:
            value: The string value to convert.
            
        Returns:
            Converted value (int, float, bool, or string).
        """
        # Boolean
        if value.lower() in ("true", "yes", "on", "1"):
            return True
        if value.lower() in ("false", "no", "off", "0"):
            return False
            
        # Integer
        try:
            return int(value)
        except ValueError:
            pass
            
        # Float
        try:
            return float(value)
        except ValueError:
            pass
            
        return value
        
    def format_response(self, response: Dict[str, Any]) -> bytes:
        """Format a response dictionary as XPA protocol bytes.
        
        Args:
            response: The response dictionary to format.
            
        Returns:
            Formatted response as bytes.
        """
        status = response.get("status", "ok")
        
        if status == "ok":
            result = response.get("result", "")
            text = str(result) if result else ""
        else:
            message = response.get("message", "Unknown error")
            text = f"ERROR: {message}"
            
        return (text + "\n").encode(self.ENCODING)
        
    def format_error(self, message: str) -> bytes:
        """Format an error response.
        
        Args:
            message: The error message.
            
        Returns:
            Formatted error response as bytes.
        """
        return f"ERROR: {message}\n".encode(self.ENCODING)
        
    def create_message(
        self,
        msg_type: XPAMessageType,
        target: str,
        command: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[bytes] = None,
    ) -> XPAMessage:
        """Create an XPA message object.
        
        Args:
            msg_type: The message type.
            target: The target access point.
            command: The command to execute.
            params: Optional parameters dictionary.
            data: Optional binary data payload.
            
        Returns:
            XPAMessage object.
        """
        return XPAMessage(
            msg_type=msg_type,
            target=target,
            command=command,
            params=params or {},
            data=data,
        )
        
    def serialize_message(self, message: XPAMessage) -> bytes:
        """Serialize an XPA message to bytes.
        
        Args:
            message: The XPA message to serialize.
            
        Returns:
            Serialized message as bytes.
        """
        parts: List[str] = [message.command]
        
        for key, value in message.params.items():
            if isinstance(value, bool):
                value = "yes" if value else "no"
            parts.append(f"{key}={value}")
            
        header = " ".join(parts)
        result = header.encode(self.ENCODING) + self.HEADER_TERMINATOR
        
        if message.data:
            result += message.data + self.HEADER_TERMINATOR
            
        return result
        
    def validate_command(self, command: str) -> bool:
        """Validate a command string.
        
        Args:
            command: The command to validate.
            
        Returns:
            True if the command is valid, False otherwise.
        """
        if not command:
            return False
            
        # Command should be alphanumeric with underscores
        return bool(re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', command))
        
    def get_access_info(self, name: str, host: str, port: int) -> str:
        """Get XPA access point information string.
        
        Args:
            name: The access point name.
            host: The host address.
            port: The port number.
            
        Returns:
            Access point information string.
        """
        return f"{name} {host}:{port}"
