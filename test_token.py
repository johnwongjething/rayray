#!/usr/bin/env python3
"""
Test JWT Token Script
This script will help debug JWT token issues
"""

import jwt
import json
from datetime import datetime

def test_jwt_token(token_string):
    """Test a JWT token and show its contents"""
    try:
        # Decode the token without verification first to see the payload
        decoded = jwt.decode(token_string, options={"verify_signature": False})
        
        print("✅ Token decoded successfully!")
        print(f"Token payload: {json.dumps(decoded, indent=2)}")
        
        # Check if token has expiration
        if 'exp' in decoded:
            exp_timestamp = decoded['exp']
            exp_date = datetime.fromtimestamp(exp_timestamp)
            current_date = datetime.now()
            
            print(f"Token expires at: {exp_date}")
            print(f"Current time: {current_date}")
            
            if current_date > exp_date:
                print("❌ Token has expired!")
                return False
            else:
                print("✅ Token is still valid")
                return True
        else:
            print("⚠️  Token has no expiration time")
            return True
            
    except jwt.InvalidTokenError as e:
        print(f"❌ Invalid token: {e}")
        return False
    except Exception as e:
        print(f"❌ Error decoding token: {e}")
        return False

if __name__ == "__main__":
    print("JWT Token Tester")
    print("================")
    
    # You can paste your token here for testing
    token = input("Enter your JWT token (or press Enter to skip): ").strip()
    
    if token:
        test_jwt_token(token)
    else:
        print("No token provided. You can test tokens by running this script and pasting your token.") 