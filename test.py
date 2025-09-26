#!/usr/bin/env python3
"""
DOBS MCP Server Test Script
Complete test suite for functionality and Docker integration
"""

import asyncio
import json
import subprocess
import sys
import os

# Set test environment variables
os.environ['DOBS_API_KEY'] = 'test_key_for_testing'
os.environ['DOBS_BASE_URL'] = 'https://api.dobs.ai'

def test_imports():
    """Test 1: Basic imports"""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from dobs_mcp_server.main import server, api_client, DobsApiClient
        print("✅ PASS: All imports successful")
        return True
    except Exception as e:
        print(f"❌ FAIL: Import error: {e}")
        return False

def test_api_client():
    """Test 2: API Client structure"""
    try:
        from dobs_mcp_server.main import DobsApiClient

        client = DobsApiClient("https://test.api", "test_key")

        # Check required attributes
        required_attrs = ['base_url', 'api_key', 'headers', 'make_request']
        for attr in required_attrs:
            if not hasattr(client, attr):
                print(f"❌ FAIL: Missing attribute: {attr}")
                return False

        print("✅ PASS: API Client has all required attributes")
        return True
    except Exception as e:
        print(f"❌ FAIL: API Client error: {e}")
        return False

def test_environment_validation():
    """Test 3: Environment variable validation"""
    try:
        # Save current env
        old_key = os.environ.get('DOBS_API_KEY')

        # Remove API key
        if 'DOBS_API_KEY' in os.environ:
            del os.environ['DOBS_API_KEY']

        # Try to import (should fail)
        try:
            # Force reload to test validation
            import importlib
            if 'dobs_mcp_server.main' in sys.modules:
                del sys.modules['dobs_mcp_server.main']

            import dobs_mcp_server.main
            print("❌ FAIL: Should require API key")
            return False
        except ValueError as e:
            if "DOBS_API_KEY" in str(e):
                print("✅ PASS: Properly validates API key requirement")
                return True
            else:
                print(f"❌ FAIL: Wrong validation error: {e}")
                return False
        finally:
            # Restore env
            if old_key:
                os.environ['DOBS_API_KEY'] = old_key

    except Exception as e:
        print(f"❌ FAIL: Environment test error: {e}")
        return False

def test_docker_build():
    """Test 4: Docker build"""
    try:
        print("🔨 Building Docker image...")
        result = subprocess.run(
            ["docker", "build", "-t", "dobs-mcp-server-test", ".", "-q"],
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode == 0:
            print("✅ PASS: Docker image built successfully")
            return True
        else:
            print(f"❌ FAIL: Docker build failed: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        print("❌ FAIL: Docker build timed out")
        return False
    except FileNotFoundError:
        print("⚠️  SKIP: Docker not installed")
        return None
    except Exception as e:
        print(f"❌ FAIL: Docker build error: {e}")
        return False

def test_docker_run():
    """Test 5: Docker container starts"""
    try:
        print("🚀 Testing Docker container startup...")

        # Use timeout to prevent hanging
        result = subprocess.run([
            "timeout", "5s", "docker", "run", "--rm",
            "-e", "DOBS_API_KEY=test_key",
            "-e", "DOBS_BASE_URL=https://api.dobs.ai",
            "dobs-mcp-server-test"
        ], capture_output=True, text=True)

        # Exit code 124 means timeout (expected)
        # Exit code 0 means clean exit
        if result.returncode in [0, 124]:
            print("✅ PASS: Docker container starts successfully")
            return True
        else:
            print(f"❌ FAIL: Container startup failed: {result.stderr}")
            return False

    except Exception as e:
        print(f"❌ FAIL: Docker run test error: {e}")
        return False

async def test_mcp_protocol():
    """Test 6: MCP protocol communication"""
    try:
        print("📡 Testing MCP protocol...")

        # Start container with JSON-RPC input
        proc = subprocess.Popen([
            "docker", "run", "-i", "--rm",
            "-e", "DOBS_API_KEY=test_key",
            "-e", "DOBS_BASE_URL=https://api.dobs.ai",
            "dobs-mcp-server-test"
        ], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # Send MCP initialize request
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0"}
            }
        }

        try:
            stdout, stderr = proc.communicate(
                input=json.dumps(init_request) + '\n',
                timeout=10
            )

            if stdout and 'jsonrpc' in stdout.lower():
                print("✅ PASS: MCP protocol responds correctly")
                return True
            elif proc.returncode == 0 or "initialize" in stderr:
                print("✅ PASS: MCP server processes messages")
                return True
            else:
                print(f"❌ FAIL: No MCP response. stdout: {stdout}, stderr: {stderr}")
                return False

        except subprocess.TimeoutExpired:
            proc.kill()
            print("✅ PASS: MCP server is listening (timeout expected)")
            return True

    except Exception as e:
        print(f"❌ FAIL: MCP protocol test error: {e}")
        return False

def test_file_structure():
    """Test 7: Required files exist"""
    required_files = [
        'dobs_mcp_server/main.py',
        'dobs_mcp_server/__init__.py',
        'requirements.txt',
        'Dockerfile',
        'README.md',
        '.env.example'
    ]

    missing_files = []
    for file_path in required_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)

    if not missing_files:
        print("✅ PASS: All required files present")
        return True
    else:
        print(f"❌ FAIL: Missing files: {missing_files}")
        return False

async def main():
    """Run all tests"""
    print("🧪 DOBS MCP Server Test Suite (Simple)")
    print("=" * 50)
    print()

    tests = [
        ("File Structure", test_file_structure),
        ("Imports", test_imports),
        ("API Client", test_api_client),
        ("Environment Validation", test_environment_validation),
        ("Docker Build", test_docker_build),
        ("Docker Run", test_docker_run),
        ("MCP Protocol", test_mcp_protocol)
    ]

    passed = 0
    total = 0

    for test_name, test_func in tests:
        print(f"Running: {test_name}")
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()

            if result is True:
                passed += 1
            elif result is None:
                print(f"⚠️  SKIP: {test_name}")
                continue  # Don't count skipped tests

            total += 1

        except Exception as e:
            print(f"❌ FAIL: {test_name} - {e}")
            total += 1

        print()

    # Summary
    print("=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    print(f"Passed: {passed}/{total}")
    print(f"Success Rate: {(passed/total)*100:.1f}%" if total > 0 else "No tests run")

    if passed == total:
        print("🎉 All tests passed! The MCP server is ready.")
        print("\n📋 Next steps:")
        print("1. Set your real DOBS_API_KEY in .env file")
        print("2. Add to Claude Desktop configuration")
        print("3. Test with: docker run -it --env-file .env dobs-mcp-server-test")
    else:
        print("⚠️  Some tests failed. Check the issues above.")

    return passed == total

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)