import csv
import pytest
from pathlib import Path
from scripts.convert_bb_lc import parse_input

@pytest.fixture
def sample_input(tmp_path):
    """Creates a sample BB statement file for testing."""
    content = """\
                                    SISBB - Sistema de Informações Banco do Brasil                                   
                                      04/10/2025 - Autoatendimento BB - 17:52:21                                     
                                          Agência: 1234-5 - Conta: 123456-X                                          
                                            Cliente: FULANO                                           

---------------------------------------------------------------------------------------------------------------------
                                                   LCA SELECIONADA                                                   
---------------------------------------------------------------------------------------------------------------------
        NÚMERO:               5293462534625934
        DATA APLICAÇÃO:   07/04/2025
        VALOR DE EMISSÃO: 30.000,00                                         
        SALDO:            31.961,95                                         
        TAXA:             93,00                                             
        DATA VENCIMENTO:  16/03/2029                                        
---------------------------------------------------------------------------------------------------------------------
                                              EXTRATO REF AO MÊS 04/2025                                             
---------------------------------------------------------------------------------------------------------------------
   DATA        HISTÓRICO       VALOR DE CAPITAL      IR          IOF      RENDIMENTOS   VALOR MOVIMENTO   VALOR ATUAL 
---------------------------------------------------------------------------------------------------------------------
 31/03/2025 Saldo Anterior                 0,00        0,00        0,00           0,00             0,00             0
 07/04/2025 Aplicação                 30.000,00        0,00        0,00           0,00        30.000,00       3000000
 30/04/2025 Saldo Atual               30.000,00        0,00        0,00         220,59             0,00       3022059

                                                         ------------------------------------------------------------
                                                                                 RESUMO DO MÊS
                                                         ------------------------------------------------------------
                                                                SALDO ANTERIOR                               0,00
                                                                APLICAÇÃO                               30.000,00
                                                                RESGATES                                     0,00
                                                                RENDIMENTO BRUTO                           220,59
                                                                IMPOSTO DE RENDA                             0,00
                                                                IOF                                          0,00
                                                                RENDIMENTO LIQUÍDO                         220,59
                                                                SALDO ATUAL                             30.220,59
"""
    input_path = tmp_path / "bb-lcilca.txt"
    input_path.write_text(content, encoding="utf-8")
    return input_path


SAMPLES_DIR = Path(__file__).parent.parent / "samples"

def test_extract_bb_statement_creates_expected_csv(sample_input, tmp_path):
    """Test if the extractor generates correct CSV output."""
    sample_file = SAMPLES_DIR / "bb-lcilca.txt"

    fieldnames, records = parse_input(sample_file)

    # Validate header
    assert fieldnames == ["Data", "Histórico", "Valor Movimento"]

    # Should have exactly 2 data lines (Aplicação + Rendimento Bruto)
    assert len(records) == 2

    # Validate first row (from table)
    assert records[0][0] == "07/04/2025"
    assert records[0][1] == "Aplicação"
    assert records[0][2] == "30000,00"

    # Validate second row (from summary)
    assert records[1][0] == "30/04/2025"
    assert records[1][1] == "Rendimento Bruto"
    assert records[1][2] == "220,59"

    # Ensure "Saldo Anterior" and "Saldo Atual" were ignored
    historicos = [row[1].lower() for row in records]
    assert not any("saldo" in h for h in historicos)
