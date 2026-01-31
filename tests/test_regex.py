"""
Testes para o Motor de Regex
"""
import pytest
from app.core.regex_matcher import regex_matcher, RegexMatcher


class TestRegexMatcher:
    """Testes para padrões de regex"""
    
    def test_cpf_with_punctuation(self):
        """Testa detecção de CPF com pontuação"""
        text = "O CPF do cliente é 123.456.789-09"
        matches = regex_matcher.find_by_type(text, "CPF")
        
        assert len(matches) == 1
        assert matches[0].valor == "123.456.789-09"
    
    def test_cpf_without_punctuation(self):
        """Testa detecção de CPF sem pontuação"""
        text = "CPF: 12345678909"
        matches = regex_matcher.find_by_type(text, "CPF")
        
        assert len(matches) == 1
        assert matches[0].valor == "12345678909"
    
    def test_cnpj_with_punctuation(self):
        """Testa detecção de CNPJ com pontuação"""
        text = "CNPJ: 12.345.678/0001-90"
        matches = regex_matcher.find_by_type(text, "CNPJ")
        
        assert len(matches) == 1
        assert matches[0].valor == "12.345.678/0001-90"
    
    def test_cnpj_without_punctuation(self):
        """Testa detecção de CNPJ sem pontuação"""
        text = "CNPJ 12345678000190"
        matches = regex_matcher.find_by_type(text, "CNPJ")
        
        assert len(matches) == 1
        assert matches[0].valor == "12345678000190"
    
    def test_proc_cnj(self):
        """Testa detecção de número de processo CNJ"""
        text = "Processo nº 0000123-45.2024.8.13.0024"
        matches = regex_matcher.find_by_type(text, "PROC_CNJ")
        
        assert len(matches) == 1
        assert matches[0].valor == "0000123-45.2024.8.13.0024"
    
    def test_oab_variations(self):
        """Testa diferentes formatos de OAB"""
        texts = [
            "OAB/MG 123456",
            "OAB-MG 123.456",
            "OAB 123456",
            "oab/mg 123456",
        ]
        
        for text in texts:
            matches = regex_matcher.find_by_type(text, "OAB")
            assert len(matches) == 1, f"Falhou para: {text}"
    
    def test_email(self):
        """Testa detecção de e-mail"""
        text = "Contato: joao.silva@tribunal.jus.br"
        matches = regex_matcher.find_by_type(text, "EMAIL")
        
        assert len(matches) == 1
        assert matches[0].valor == "joao.silva@tribunal.jus.br"
    
    def test_telefone_celular(self):
        """Testa detecção de telefone celular"""
        texts = [
            "(31) 99999-1234",
            "31 99999-1234",
            "+55 31 999991234",
        ]
        
        for text in texts:
            matches = regex_matcher.find_by_type(text, "TELEFONE")
            assert len(matches) >= 1, f"Falhou para: {text}"
    
    def test_cep(self):
        """Testa detecção de CEP"""
        texts = [
            "CEP: 30123-456",
            "CEP 30.123-456",
            "CEP: 30123456",
        ]
        
        for text in texts:
            matches = regex_matcher.find_by_type(text, "CEP")
            assert len(matches) == 1, f"Falhou para: {text}"
    
    def test_rg_with_context(self):
        """Testa detecção de RG com contexto"""
        text = "RG: MG-12.345.678"
        matches = regex_matcher.find_by_type(text, "RG")
        
        assert len(matches) == 1
    
    def test_find_all(self):
        """Testa busca de múltiplos padrões"""
        text = """
        Cliente: João Silva
        CPF: 123.456.789-09
        E-mail: joao@email.com
        Telefone: (31) 99999-1234
        """
        
        matches = regex_matcher.find_all(text)
        types_found = {m.tipo for m in matches}
        
        assert "CPF" in types_found
        assert "EMAIL" in types_found
        assert "TELEFONE" in types_found
    
    def test_validate_cpf_valid(self):
        """Testa validação de CPF válido"""
        # CPF válido de exemplo
        assert regex_matcher.validate_cpf("529.982.247-25") is True
    
    def test_validate_cpf_invalid(self):
        """Testa validação de CPF inválido"""
        assert regex_matcher.validate_cpf("111.111.111-11") is False
        assert regex_matcher.validate_cpf("123.456.789-00") is False
    
    def test_validate_cnpj_valid(self):
        """Testa validação de CNPJ válido"""
        # CNPJ válido de exemplo
        assert regex_matcher.validate_cnpj("11.222.333/0001-81") is True
    
    def test_validate_cnpj_invalid(self):
        """Testa validação de CNPJ inválido"""
        assert regex_matcher.validate_cnpj("11.111.111/1111-11") is False
    
    def test_get_context(self):
        """Testa extração de contexto"""
        text = "O cliente João da Silva possui CPF 123.456.789-09 registrado no sistema."
        
        context = regex_matcher.get_context(text, 35, 49, janela=15)
        
        assert "123.456.789-09" in context
        assert "..." in context


class TestEdgeCases:
    """Testes de casos extremos"""
    
    def test_empty_text(self):
        """Testa texto vazio"""
        matches = regex_matcher.find_all("")
        assert len(matches) == 0
    
    def test_no_matches(self):
        """Testa texto sem dados sensíveis"""
        text = "Este é um texto sem dados sensíveis."
        matches = regex_matcher.find_all(text)
        assert len(matches) == 0
    
    def test_multiple_same_type(self):
        """Testa múltiplos itens do mesmo tipo"""
        text = "CPF 1: 123.456.789-09, CPF 2: 987.654.321-00"
        matches = regex_matcher.find_by_type(text, "CPF")
        assert len(matches) == 2
    
    def test_invalid_type(self):
        """Testa tipo de dado inválido"""
        with pytest.raises(ValueError):
            regex_matcher.find_by_type("texto", "INVALIDO")
