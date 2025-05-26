import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
from session_management import (
    GlobalSession,
    GlobalSessionManager,
    session_manager,
    get_session
)
from app import app

@pytest.fixture
def test_client():
    return TestClient(app)

@pytest.fixture
def session_mgr():
    return GlobalSessionManager(session_timeout_minutes=1)

class TestSessionManagement:
    def test_create_session(self, session_mgr):
        session_id = session_mgr.create_session()
        assert session_id is not None
        assert session_id in session_mgr.sessions
        assert isinstance(session_mgr.sessions[session_id], GlobalSession)

    def test_get_session(self, session_mgr):
        session_id = session_mgr.create_session()
        session = session_mgr.get_session(session_id)
        assert session is not None
        assert isinstance(session, GlobalSession)

    def test_session_timeout(self, session_mgr):
        session_id = session_mgr.create_session()
        session = session_mgr.sessions[session_id]
        # Manually set last_accessed to simulate timeout
        session.last_accessed = datetime.now() - timedelta(minutes=2)
        session_mgr.cleanup_old_sessions()
        assert session_id not in session_mgr.sessions

    def test_session_access_updates_timestamp(self, session_mgr):
        session_id = session_mgr.create_session()
        original_time = session_mgr.sessions[session_id].last_accessed
        # Small delay
        import time
        time.sleep(0.1)
        session_mgr.get_session(session_id)
        new_time = session_mgr.sessions[session_id].last_accessed
        assert new_time > original_time

class TestSessionAPI:
    def test_initialize_session(self, test_client):
        # Log request details
        print("\n=== Test Request Details ===")
        print("Base URL:", test_client.base_url)
        print("Full URL:", str(test_client.base_url) + "/api/session/init")
        print("Headers:", test_client.headers)
        
        response = test_client.post("/api/session/init")
        
        # Log response details
        print("\n=== Test Response Details ===")
        print(f"Status Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        print(f"Raw Content: {response.content}")
        print(f"Request URL: {response.url}")
        
        # Try to get response text
        try:
            print(f"Response Text: {response.text}")
        except Exception as e:
            print(f"Error getting response text: {e}")
        
        # Try to get JSON
        try:
            print(f"Response JSON: {response.json()}")
        except Exception as e:
            print(f"Error parsing JSON: {e}")
        
        # Print middleware information
        print("\n=== Application Middleware ===")
        for middleware in test_client.app.user_middleware:
            print(f"Active Middleware: {middleware.cls.__name__}")
        
        assert response.status_code == 200
        assert "session_id" in response.json()
        assert "status" in response.json()
        assert response.json()["status"] == "success"

    def test_get_session_status(self, test_client):
        # First create a session
        init_response = test_client.post("/api/session/init")
        # Log response details
        print("\n=== Test Response Details ===")
        print(f"Status Code: {init_response.status_code}")
        print(f"Headers: {dict(init_response.headers)}")
        print(f"Raw Content: {init_response.content}")
        print(f"Request URL: {init_response.url}")
        session_id = init_response.json()["session_id"]

        print(f"Session ID: {session_id}")
        
        # Test status endpoint
        response = test_client.get(
            "/api/session/status",
            headers={"X-Session-ID": session_id}
        )
        # Log response details
        print("\n=== Status Response Details ===")
        print(f"Status Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        print(f"Raw Content: {response.content}")
        print(f"Request URL: {response.url}")
        assert response.status_code == 200
        status_data = response.json()
        assert "active" in status_data
        assert "last_accessed" in status_data
        assert "has_ruleslawyer" in status_data
        assert "has_storegenerator" in status_data
        assert "has_cardgenerator" in status_data

    def test_validate_session(self, test_client):
        # Create a session
        init_response = test_client.post("/api/session/init")
        session_id = init_response.json()["session_id"]
        
        # Test validation
        response = test_client.get(f"/api/session/validate/{session_id}")
        assert response.status_code == 200
        assert response.json()["valid"] is True

    def test_invalid_session(self, test_client):
        response = test_client.get("/api/session/validate/invalid-session-id")
        assert response.status_code == 200
        assert response.json()["valid"] is False

    def test_session_cleanup(self, test_client):
        response = test_client.delete("/api/session/cleanup")
        assert response.status_code == 200
        assert "initial_sessions" in response.json()
        assert "remaining_sessions" in response.json()

    def test_session_info(self, test_client):
        # Create a session
        init_response = test_client.post("/api/session/init")
        session_id = init_response.json()["session_id"]
        
        # Test info endpoint
        response = test_client.get(f"/api/session/info/{session_id}")
        assert response.status_code == 200
        info = response.json()
        assert "session_id" in info
        assert "last_accessed" in info
        assert "active_services" in info
        assert "user_id" in info

class TestSessionIntegration:
    def test_session_with_ruleslawyer(self, test_client):
        # Initialize session
        init_response = test_client.post("/api/session/init")
        session_id = init_response.json()["session_id"]
        
        # Make a ruleslawyer request
        response = test_client.post(
            "/api/ruleslawyer/query",
            json={"message": "test query"},
            headers={"X-Session-ID": session_id}
        )
        assert response.status_code == 200

        # Check session info
        info_response = test_client.get(f"/api/session/info/{session_id}")
        assert info_response.json()["active_services"]["ruleslawyer"] is True

    def test_session_persistence(self, test_client):
        # Create session
        init_response = test_client.post("/api/session/init")
        session_id = init_response.json()["session_id"]
        
        # Make multiple requests
        for _ in range(3):
            response = test_client.get(
                "/api/session/status",
                headers={"X-Session-ID": session_id}
            )
            assert response.status_code == 200
            assert response.json()["active"] is True 