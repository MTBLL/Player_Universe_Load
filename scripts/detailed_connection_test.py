#!/usr/bin/env python3
"""
Detailed connection test for PostgreSQL database
"""
import socket
import time
import sys
import errno
from typing import Dict, Union, Optional, Any

def get_error_message(error_code: int) -> str:
    """Convert socket error code to message"""
    error_messages: Dict[int, str] = {
        errno.ECONNREFUSED: "Connection refused",
        errno.ETIMEDOUT: "Connection timed out",
        errno.ECONNRESET: "Connection reset by peer",
        errno.ENOTSOCK: "Socket operation on non-socket",
        errno.ENETUNREACH: "Network is unreachable",
        35: "Resource temporarily unavailable"  # Common on macOS
    }
    return error_messages.get(error_code, f"Unknown error ({error_code})")

def test_postgres_connection(host: str, port: int = 5432, timeout: int = 10) -> bool:
    """Test PostgreSQL connection with detailed diagnostics"""
    print(f"Testing connection to {host}:{port} with timeout {timeout}s")
    
    # DNS resolution test
    try:
        print(f"Resolving hostname {host}...")
        start_time = time.time()
        ip_address = socket.gethostbyname(host)
        resolution_time = time.time() - start_time
        print(f"Hostname resolved to {ip_address} in {resolution_time:.2f}s")
    except socket.gaierror as e:
        print(f"Error resolving hostname: {e}")
        return False
    
    # Socket connection test
    try:
        print(f"Attempting to connect to {ip_address}:{port}...")
        start_time = time.time()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        result = s.connect_ex((ip_address, port))
        connection_time = time.time() - start_time
        
        if result == 0:
            print(f"Successfully connected in {connection_time:.2f}s")
            s.close()
            return True
        else:
            print(f"Connection failed with error code {result}")
            print(f"Error message: {get_error_message(result)}")
            return False
    except socket.error as e:
        print(f"Socket error: {e}")
        return False

if __name__ == "__main__":
    host = "mtbl.chigsmi0ar1o.us-west-1.rds.amazonaws.com"
    port = 5432
    
    print("========== PostgreSQL Connection Test ==========")
    success = test_postgres_connection(host, port)
    
    if success:
        print("Connection test passed!")
        sys.exit(0)
    else:
        print("Connection test failed!")
        print("\nPossible issues:")
        print("1. Security group rules not allowing connections from your IP")
        print("2. Network ACLs blocking traffic")
        print("3. RDS instance not running or still initializing")
        print("4. Local firewall blocking outbound connections")
        sys.exit(1)