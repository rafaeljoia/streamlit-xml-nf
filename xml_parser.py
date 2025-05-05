# -*- coding: utf-8 -*-
"""Módulo para processar arquivos XML grandes e extrair dados de tags específicas,
com suporte opcional a filtragem condicional (incluindo tags em níveis diferentes)."""

import os
from lxml import etree
from collections import Counter
import io

def extract_tag_data(xml_source, tag_name):
    """Processa um arquivo/stream XML e extrai valores/contagens de uma tag específica.

    Args:
        xml_source: Caminho para o arquivo XML (str) ou um objeto file-like.
        tag_name: O nome da tag a ser buscada (sem namespace).

    Returns:
        Um Counter com os valores da tag como chaves e suas contagens como valores,
        ou None se ocorrer um erro.
    """
    tag_values_counter = Counter()
    try:
        context = etree.iterparse(xml_source, events=("end",), tag=tag_name, recover=True)
        for event, elem in context:
            text_content = elem.text.strip() if elem.text else ""
            tag_values_counter[text_content] += 1
            elem.clear()
            while elem.getprevious() is not None:
                del elem.getparent()[0]
        return tag_values_counter
    except etree.XMLSyntaxError as e:
        print(f"Erro de sintaxe XML: {e}")
        return None
    except Exception as e:
        print(f"Erro inesperado (extract_tag_data): {e}")
        return None

def extract_filtered_tag_data(xml_source, common_ancestor_tag, filter_tag, filter_value, target_tag):
    """Processa XML, filtrando por valor de tag e extraindo outra tag sob o mesmo ancestral comum.

    Permite que filter_tag e target_tag estejam em diferentes "galhos" sob o common_ancestor_tag.

    Args:
        xml_source: Caminho para o arquivo XML (str) ou um objeto file-like.
        common_ancestor_tag: Tag ancestral que contém (direta ou indiretamente) a tag de filtro e a tag alvo.
        filter_tag: Tag usada para filtrar.
        filter_value: Valor que a filter_tag deve ter.
        target_tag: Tag cujo valor será extraído se o filtro corresponder.

    Returns:
        Um Counter com os valores da target_tag como chaves e suas contagens como valores,
        ou None se ocorrer um erro.
    """
    target_values_counter = Counter()
    try:
        # Iterar sobre a tag ancestral comum
        context = etree.iterparse(xml_source, events=("end",), tag=common_ancestor_tag, recover=True)
        for event, ancestor_elem in context:
            filter_match = False
            target_value = None

            # Buscar a tag de filtro em qualquer lugar abaixo do ancestral
            # Usamos .find() que busca o primeiro descendente com esse nome.
            # Se precisar de mais controle (ex: múltiplos filter_tag), XPath seria necessário.
            filter_elem = ancestor_elem.find(f'.//{filter_tag}')
            if filter_elem is not None and filter_elem.text and filter_elem.text.strip() == filter_value:
                filter_match = True

            # Se o filtro correspondeu, buscar a tag alvo em qualquer lugar abaixo do MESMO ancestral
            if filter_match:
                target_elem = ancestor_elem.find(f'.//{target_tag}')
                if target_elem is not None and target_elem.text:
                    target_value = target_elem.text.strip()
                else:
                    # Se a tag alvo não for encontrada ou estiver vazia após o filtro bater
                    target_value = "[TAG ALVO NÃO ENCONTRADA/VAZIA NO CONTEXTO]"

                # Adicionar ao contador se um valor alvo foi encontrado (ou o marcador)
                target_values_counter[target_value] += 1

            # Limpeza de memória crucial
            ancestor_elem.clear()
            while ancestor_elem.getprevious() is not None:
                del ancestor_elem.getparent()[0]

        return target_values_counter
    except etree.XMLSyntaxError as e:
        print(f"Erro de sintaxe XML: {e}")
        return None
    except Exception as e:
        print(f"Erro inesperado (extract_filtered_tag_data): {e}")
        return None

def process_files(files, tag_name, parent_tag=None, filter_tag=None, filter_value=None):
    """Processa arquivos XML, aplicando filtro (simples ou aninhado) se especificado.

    Args:
        files: Lista de UploadedFile ou caminhos de arquivo.
        tag_name: Tag alvo.
        parent_tag: (Opcional) Tag ancestral comum para contexto de filtro.
        filter_tag: (Opcional) Tag para filtrar.
        filter_value: (Opcional) Valor da tag de filtro.

    Returns:
        Lista de dicionários com os resultados.
    """
    results = []
    is_filtering = bool(parent_tag and filter_tag and filter_value)
    target_tag_name = tag_name

    for uploaded_file in files:
        file_name = getattr(uploaded_file, 'name', str(uploaded_file))
        tag_data = None
        filter_description = f"{filter_tag}={filter_value} (contexto: {parent_tag})" if is_filtering else "Nenhum"

        try:
            source_arg = None
            if hasattr(uploaded_file, 'getvalue'):
                # Resetar o ponteiro do BytesIO a cada uso
                uploaded_file.seek(0)
                source_arg = io.BytesIO(uploaded_file.getvalue())
            elif isinstance(uploaded_file, str) and os.path.exists(uploaded_file):
                source_arg = uploaded_file
            else:
                print(f"Fonte de arquivo inválida: {file_name}")
                results.append({
                    'Nome do Arquivo': file_name, 'TAG': target_tag_name,
                    'Filtro': filter_description, 'Valor': '[ARQUIVO INVÁLIDO]', 'Ocorrência': 0
                })
                continue

            # Escolher a função de extração
            if is_filtering:
                tag_data = extract_filtered_tag_data(source_arg, parent_tag, filter_tag, filter_value, target_tag_name)
            else:
                tag_data = extract_tag_data(source_arg, target_tag_name)

            # Processar resultados
            if tag_data is not None:
                if not tag_data:
                    results.append({
                        'Nome do Arquivo': file_name, 'TAG': target_tag_name,
                        'Filtro': filter_description, 'Valor': '[NENHUM VALOR ENCONTRADO COM ESTES CRITÉRIOS]', 'Ocorrência': 0
                    })
                else:
                    for value, count in tag_data.items():
                        results.append({
                            'Nome do Arquivo': file_name, 'TAG': target_tag_name,
                            'Filtro': filter_description, 'Valor': value, 'Ocorrência': count
                        })
            else: # Erro durante o processamento
                 results.append({
                     'Nome do Arquivo': file_name, 'TAG': target_tag_name,
                     'Filtro': filter_description, 'Valor': '[ERRO AO PROCESSAR XML]', 'Ocorrência': 0
                 })

        except Exception as e:
            print(f"Erro geral ao processar arquivo {file_name}: {e}")
            results.append({
                'Nome do Arquivo': file_name, 'TAG': target_tag_name,
                'Filtro': filter_description, 'Valor': '[ERRO INESPERADO NO PROCESSAMENTO]', 'Ocorrência': 0
            })
        finally:
            # Fechar o BytesIO se foi criado
            if isinstance(source_arg, io.BytesIO):
                source_arg.close()

    return results

# Exemplo de uso
if __name__ == '__main__':
    # XML com estrutura aninhada para teste de filtro
    xml_nested_test = """
    <documento>
        <NFCom>
            <infNFCom>
                <ide>
                    <cUF>31</cUF> <!-- MG -->
                    <nNF>1001</nNF>
                </ide>
                <emit>
                    <xNome>Empresa MG</xNome>
                    <enderEmit>
                        <UF>MG</UF>
                    </enderEmit>
                </emit>
            </infNFCom>
        </NFCom>
        <NFCom>
            <infNFCom>
                <ide>
                    <cUF>35</cUF> <!-- SP -->
                    <nNF>1002</nNF>
                </ide>
                <emit>
                    <xNome>Empresa SP</xNome>
                    <enderEmit>
                        <UF>SP</UF>
                    </enderEmit>
                </emit>
            </infNFCom>
        </NFCom>
        <NFCom>
            <infNFCom>
                <ide>
                    <cUF>31</cUF> <!-- MG -->
                    <nNF>1003</nNF>
                </ide>
                <emit>
                    <xNome>Outra Empresa MG</xNome>
                    <enderEmit>
                        <UF>MG</UF>
                    </enderEmit>
                </emit>
            </infNFCom>
        </NFCom>
         <NFCom>
            <infNFCom>
                <ide>
                    <cUF>35</cUF> <!-- SP -->
                    <nNF>1004</nNF> <!-- Outro nNF para SP -->
                </ide>
                <emit>
                    <xNome>Outra Empresa SP</xNome>
                    <enderEmit>
                        <UF>SP</UF>
                    </enderEmit>
                </emit>
            </infNFCom>
        </NFCom>
    </documento>
    """
    with open("exemplo_aninhado.xml", "w", encoding="utf-8") as f:
        f.write(xml_nested_test)

    print("--- Teste Aninhado SEM Filtro (nNF) ---")
    results_nnf = process_files(["exemplo_aninhado.xml"], "nNF")
    print(results_nnf)

    print("\n--- Teste Aninhado COM Filtro (nNF onde UF=SP dentro de infNFCom) ---")
    # Ancestral comum: infNFCom, Filtro: UF='SP', Alvo: nNF
    results_filtered_sp = process_files(["exemplo_aninhado.xml"], tag_name="nNF", parent_tag="infNFCom", filter_tag="UF", filter_value="SP")
    print(results_filtered_sp)

    print("\n--- Teste Aninhado COM Filtro (nNF onde UF=MG dentro de infNFCom) ---")
    results_filtered_mg = process_files(["exemplo_aninhado.xml"], tag_name="nNF", parent_tag="infNFCom", filter_tag="UF", filter_value="MG")
    print(results_filtered_mg)

    print("\n--- Teste Aninhado COM Filtro (xNome onde UF=SP dentro de infNFCom) ---")
    results_filtered_xnome = process_files(["exemplo_aninhado.xml"], tag_name="xNome", parent_tag="infNFCom", filter_tag="UF", filter_value="SP")
    print(results_filtered_xnome)

    print("\n--- Teste Aninhado COM Filtro (nNF onde UF=RJ - inexistente) ---")
    results_no_match_rj = process_files(["exemplo_aninhado.xml"], tag_name="nNF", parent_tag="infNFCom", filter_tag="UF", filter_value="RJ")
    print(results_no_match_rj)

    # Limpar arquivo de exemplo
    # os.remove("exemplo_aninhado.xml")

