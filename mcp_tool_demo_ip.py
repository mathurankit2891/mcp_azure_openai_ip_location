import sys
import json
import urllib.request

# Dummy model class to represent TextContent for validation purposes
class TextContent:
    def __init__(self, text: str):
        self.type = "text"  # Ensure the type field is included
        self.text = text

    def to_dict(self):
        return {"type": self.type, "text": self.text}

def get_location(ip):
    """Fetch location info for a given IP using ipinfo.io"""
    with urllib.request.urlopen(f"https://ipinfo.io/{ip}/json") as response:
        return json.loads(response.read())

def main():
    # Log to stderr for debugging
    print("[TOOL DEBUG] Tool started", file=sys.stderr)

    # Send tool metadata to MCP (tool details)
    sys.stdout.write(json.dumps({
        "type": "toolDetails",
        "tools": [{
            "name": "ip_location_lookup",
            "description": "Returns location info for a given IP address using ipinfo.io",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "ip": {"type": "string"}
                },
                "required": ["ip"]
            }
        }]
    }) + "\n")
    sys.stdout.flush()

    # Process tool calls
    for line in sys.stdin:
        try:
            # Read the incoming JSON request from stdin
            request = json.loads(line)
            print(f"[TOOL DEBUG] Received line: {line.strip()}", file=sys.stderr)

            # Handle the tools/list method
            if request.get("method") == "tools/list":
                response = {
                    "jsonrpc": "2.0",
                    "id": request["id"],
                    "result": {
                        "tools": [
                            {
                                "name": "ip_location_lookup",
                                "description": "Returns location info for a given IP address using ipinfo.io",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "ip": {"type": "string"}
                                    },
                                    "required": ["ip"]
                                }
                            }
                        ]
                    }
                }
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
                continue

            # Handle the tool call (method for querying location)
            if request.get("method") == "tools/call":
                tool_name = request.get("params", {}).get("name")
                tool_arguments = request.get("params", {}).get("arguments", {})

                # Check if we have the correct tool and arguments
                if tool_name == "ip_location_lookup" and tool_arguments:
                    ip = tool_arguments.get("ip")
                    if ip:
                        try:
                            # Fetch location data from ipinfo.io
                            location_data = get_location(ip)
                            # Ensure the content is an instance of TextContent
                            content = TextContent(json.dumps(location_data))
                            response = {
                                "jsonrpc": "2.0",
                                "id": request["id"],
                                "result": {
                                    "content": [content.to_dict()]  # Wrap in a list of the correct model
                                }
                            }
                        except Exception as api_err:
                            # In case of error, format the error message as TextContent
                            content = TextContent(f"API error: {str(api_err)}")
                            response = {
                                "jsonrpc": "2.0",
                                "id": request["id"],
                                "result": {
                                    "content": [content.to_dict()]  # Wrap in a list of the correct model
                                }
                            }
                    else:
                        # Missing IP case, format as TextContent
                        content = TextContent("Missing 'ip' in input")
                        response = {
                            "jsonrpc": "2.0",
                            "id": request["id"],
                            "result": {
                                "content": [content.to_dict()]  # Wrap in a list of the correct model
                            }
                        }
                else:
                    # Invalid tool case, format as TextContent
                    content = TextContent("Invalid tool name or missing arguments")
                    response = {
                        "jsonrpc": "2.0",
                        "id": request["id"],
                        "result": {
                            "content": [content.to_dict()]  # Wrap in a list of the correct model
                        }
                    }

                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()

        except Exception as e:
            # Error handling if the tool fails to process the request correctly
            content = TextContent(f"Error parsing input: {str(e)}")
            response = {
                "jsonrpc": "2.0",
                "id": request.get("id", 0),
                "result": {
                    "content": [content.to_dict()]  # Wrap in a list of the correct model
                }
            }
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()

if __name__ == "__main__":
    main()
