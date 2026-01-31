"""
Testes para a API FastAPI
"""
import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import tempfile

from app.main import app


client = TestClient(app)


class TestHealthCheck:
    """Testes do endpoint de health check"""
    
    def test_health_check(self):
        """Testa endpoint de health check"""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data


class TestAllowlistAPI:
    """Testes da API de allowlist"""
    
    def test_list_allowlist_empty(self):
        """Testa listagem de allowlist vazia"""
        response = client.get("/api/allowlist")
        
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
    
    def test_add_to_allowlist(self):
        """Testa adição à allowlist"""
        response = client.post("/api/allowlist", json={
            "nome": "Dr. Teste",
            "tipo": "juiz",
            "registro": "12345",
            "ativo": True
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "adicionado" in data["message"]
    
    def test_get_allowlist_stats(self):
        """Testa estatísticas da allowlist"""
        response = client.get("/api/allowlist/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)


class TestAuditAPI:
    """Testes da API de auditoria"""
    
    def test_audit_stats(self):
        """Testa estatísticas de auditoria"""
        response = client.get("/api/audit/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert "total_jobs" in data
        assert "total_redacoes" in data
    
    def test_audit_not_found(self):
        """Testa busca de job inexistente"""
        response = client.get("/api/audit/invalid-job-id")
        
        assert response.status_code == 404


class TestAnalyzeAPI:
    """Testes da API de análise"""
    
    def test_analyze_invalid_file_type(self):
        """Testa upload de arquivo com tipo inválido"""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"Conteudo de teste")
            temp_path = Path(f.name)
        
        try:
            with open(temp_path, "rb") as f:
                response = client.post(
                    "/api/analyze",
                    files={"file": ("teste.txt", f, "text/plain")}
                )
            
            assert response.status_code == 400
        finally:
            temp_path.unlink()
    
    def test_analyze_no_file(self):
        """Testa análise sem arquivo"""
        response = client.post("/api/analyze")
        
        assert response.status_code == 422  # Validation error


class TestAnonymizeAPI:
    """Testes da API de anonimização"""
    
    def test_anonymize_no_file(self):
        """Testa anonimização sem arquivo"""
        response = client.post("/api/anonymize")
        
        assert response.status_code == 422  # Validation error
    
    def test_download_not_found(self):
        """Testa download de arquivo inexistente"""
        response = client.get("/api/download/invalid-job-id")
        
        assert response.status_code == 404
