import streamlit as st
import tempfile
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import io
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, A3, letter, legal, landscape, portrait
from reportlab.lib.utils import ImageReader
import pdf2image
import subprocess
import platform
import math

# Configuração da página do Streamlit
st.set_page_config(
    page_title="Otimizador de Slides PDF",
    page_icon="📄",
    layout="wide"
)

# Dicionário de tamanhos de página
PAGE_SIZES = {
    "A4": A4,
    "A3": A3,
    "Carta (Letter)": letter,
    "Ofício (Legal)": legal
}

# Função para verificar e instalar poppler se necessário
def check_poppler():
    """Verifica se o poppler está instalado e tenta instalar se necessário."""
    try:
        # Tenta importar pdf2image e usar suas funções
        pdf2image.get_poppler_version()
        return True
    except Exception:
        st.warning("⚠️ Poppler não encontrado. Tentando instalar...")
        
        # Detecta o sistema operacional
        system = platform.system()
        
        try:
            if system == "Darwin":  # macOS
                # Verifica se o homebrew está instalado
                subprocess.run(["brew", "--version"], check=True, capture_output=True)
                # Instala poppler via homebrew
                subprocess.run(["brew", "install", "poppler"], check=True)
                st.success("✅ Poppler instalado com sucesso via Homebrew!")
                return True
            elif system == "Linux":
                # Para sistemas baseados em Debian/Ubuntu
                subprocess.run(["sudo", "apt-get", "update"], check=True)
                subprocess.run(["sudo", "apt-get", "install", "-y", "poppler-utils"], check=True)
                st.success("✅ Poppler instalado com sucesso!")
                return True
            else:
                st.error("❌ Sistema operacional não suportado para instalação automática do Poppler.")
                st.info("Por favor, instale o Poppler manualmente: https://poppler.freedesktop.org/")
                return False
        except subprocess.CalledProcessError:
            st.error("❌ Erro ao instalar Poppler. Por favor, instale manualmente.")
            if system == "Darwin":
                st.info("Para macOS: brew install poppler")
            elif system == "Linux":
                st.info("Para Linux: sudo apt-get install poppler-utils")
            return False

# Função para converter páginas PDF em imagens
def pdf_to_images(pdf_path, dpi=150):
    """Converte todas as páginas de um PDF em imagens."""
    try:
        images = pdf2image.convert_from_path(pdf_path, dpi=dpi)
        return images
    except Exception as e:
        st.error(f"Erro ao converter PDF em imagens: {str(e)}")
        return None

# Função para criar preview do layout
def create_layout_preview(config):
    """Cria uma imagem de preview do layout baseado nas configurações."""
    # Dimensões do preview (proporcionais ao papel real)
    preview_width = 400
    
    # Calcula dimensões reais da página
    page_size = PAGE_SIZES[config['page_size']]
    if config['page_orientation'] == 'Paisagem':
        real_width, real_height = landscape(page_size)
    else:
        real_width, real_height = portrait(page_size)
    
    # Calcula altura proporcional do preview
    aspect_ratio = real_height / real_width
    preview_height = int(preview_width * aspect_ratio)
    
    # Cria imagem do preview
    img = Image.new('RGB', (preview_width, preview_height), 'white')
    draw = ImageDraw.Draw(img)
    
    # Calcula margens proporcionais
    scale = preview_width / real_width
    margin_left = int(config['margin_left'] * scale * 28.35)  # cm para pixels
    margin_right = int(config['margin_right'] * scale * 28.35)
    margin_top = int(config['margin_top'] * scale * 28.35)
    margin_bottom = int(config['margin_bottom'] * scale * 28.35)
    spacing = int(config['spacing'] * scale)
    
    # Área útil
    usable_width = preview_width - margin_left - margin_right
    usable_height = preview_height - margin_top - margin_bottom
    
    # Desenha margens (área cinza claro)
    draw.rectangle([0, 0, preview_width, preview_height], fill='#f0f0f0')
    draw.rectangle([margin_left, margin_top, preview_width - margin_right, preview_height - margin_bottom], fill='white')
    
    # Calcula tamanho de cada slide
    cols = config['grid_cols']
    rows = config['grid_rows']
    
    slide_width = (usable_width - (cols - 1) * spacing) / cols
    slide_height = (usable_height - (rows - 1) * spacing) / rows
    
    # Desenha os slides
    slide_num = 1
    for row in range(rows):
        for col in range(cols):
            x = margin_left + col * (slide_width + spacing)
            y = margin_top + row * (slide_height + spacing)
            
            # Desenha retângulo do slide
            if config['show_borders']:
                draw.rectangle([x, y, x + slide_width, y + slide_height], 
                             fill='white', outline='#cccccc', width=1)
            else:
                draw.rectangle([x, y, x + slide_width, y + slide_height], 
                             fill='white', outline='#e0e0e0', width=1)
            
            # Adiciona número do slide
            try:
                # Tenta obter uma fonte padrão
                font = ImageFont.load_default()
            except:
                font = None
            
            text = f"{slide_num}"
            text_color = '#666666'
            
            # Calcula posição central do texto
            if font:
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
            else:
                text_width = len(text) * 6
                text_height = 11
            
            text_x = x + (slide_width - text_width) / 2
            text_y = y + (slide_height - text_height) / 2
            
            draw.text((text_x, text_y), text, fill=text_color, font=font)
            
            slide_num += 1
    
    # Adiciona linha tracejada na margem esquerda se for para fichário
    if config['margin_left'] >= 2.5:  # Se margem >= 2.5cm
        for y in range(margin_top, preview_height - margin_bottom, 20):
            draw.line([(margin_left - 10, y), (margin_left - 10, y + 10)], 
                     fill='#ff6666', width=2)
    
    return img

# Função para criar o PDF otimizado
def create_optimized_pdf(selected_images, output_path, config):
    """
    Cria um PDF com múltiplos slides por página baseado nas configurações.
    """
    # Obtém o tamanho da página
    page_size = PAGE_SIZES[config['page_size']]
    
    # Define orientação
    if config['page_orientation'] == 'Paisagem':
        page_width, page_height = landscape(page_size)
    else:
        page_width, page_height = portrait(page_size)
    
    # Converte margens de cm para pontos (1cm ≈ 28.35 pontos)
    margin_left = config['margin_left'] * 28.35
    margin_right = config['margin_right'] * 28.35
    margin_top = config['margin_top'] * 28.35
    margin_bottom = config['margin_bottom'] * 28.35
    spacing = config['spacing']
    
    # Grid
    cols = config['grid_cols']
    rows = config['grid_rows']
    slides_per_page = cols * rows
    
    # Calcula as dimensões de cada slide
    slide_width = (page_width - margin_left - margin_right - (cols - 1) * spacing) / cols
    slide_height = (page_height - margin_top - margin_bottom - (rows - 1) * spacing) / rows
    
    # Cria o canvas do PDF
    if config['page_orientation'] == 'Paisagem':
        c = canvas.Canvas(output_path, pagesize=landscape(page_size))
    else:
        c = canvas.Canvas(output_path, pagesize=portrait(page_size))
    
    # Processa as imagens selecionadas
    for page_idx in range(0, len(selected_images), slides_per_page):
        # Calcula posições dos slides no grid
        positions = []
        for row in range(rows):
            for col in range(cols):
                x = margin_left + col * (slide_width + spacing)
                # Y começa do topo
                y = page_height - margin_top - (row + 1) * slide_height - row * spacing
                positions.append((x, y))
        
        # Adiciona slides na página atual
        for j in range(slides_per_page):
            if page_idx + j < len(selected_images):
                img = selected_images[page_idx + j]
                
                # Aplica rotação se necessário
                if config['rotate_images'] != 0:
                    img = img.rotate(-config['rotate_images'], expand=True)
                
                # Converte PIL Image para formato compatível com reportlab
                img_buffer = io.BytesIO()
                # Salva com a qualidade especificada
                if config['image_quality'] == 'Alta':
                    quality = 95
                elif config['image_quality'] == 'Média':
                    quality = 85
                else:
                    quality = 70
                
                img.save(img_buffer, format='PNG', optimize=True, quality=quality)
                img_buffer.seek(0)
                
                # Calcula o tamanho para manter a proporção
                img_width, img_height = img.size
                aspect_ratio = img_width / img_height
                
                # Considera orientação da imagem
                if config['image_orientation'] == 'Forçar Paisagem' and aspect_ratio < 1:
                    # Rotaciona imagem retrato para paisagem
                    img = img.rotate(90, expand=True)
                    img_buffer = io.BytesIO()
                    img.save(img_buffer, format='PNG', optimize=True, quality=quality)
                    img_buffer.seek(0)
                    img_width, img_height = img_height, img_width
                    aspect_ratio = img_width / img_height
                elif config['image_orientation'] == 'Forçar Retrato' and aspect_ratio > 1:
                    # Rotaciona imagem paisagem para retrato
                    img = img.rotate(90, expand=True)
                    img_buffer = io.BytesIO()
                    img.save(img_buffer, format='PNG', optimize=True, quality=quality)
                    img_buffer.seek(0)
                    img_width, img_height = img_height, img_width
                    aspect_ratio = img_width / img_height
                
                # Ajusta dimensões mantendo proporção
                if config['fit_mode'] == 'Preencher (pode cortar)':
                    # Preenche todo o espaço, pode cortar as bordas
                    if aspect_ratio > slide_width / slide_height:
                        # Imagem é mais larga
                        draw_height = slide_height
                        draw_width = slide_height * aspect_ratio
                    else:
                        # Imagem é mais alta
                        draw_width = slide_width
                        draw_height = slide_width / aspect_ratio
                else:
                    # Ajustar (manter toda imagem visível)
                    if aspect_ratio > slide_width / slide_height:
                        # Imagem é mais larga
                        draw_width = slide_width
                        draw_height = slide_width / aspect_ratio
                    else:
                        # Imagem é mais alta
                        draw_height = slide_height
                        draw_width = slide_height * aspect_ratio
                
                # Centraliza a imagem no espaço do slide
                x_offset = (slide_width - draw_width) / 2
                y_offset = (slide_height - draw_height) / 2
                
                # Pega a posição base
                x_base, y_base = positions[j]
                
                # Calcula posição final centralizada
                x_final = x_base + x_offset
                y_final = y_base + y_offset
                
                # Desenha borda se habilitado
                if config['show_borders']:
                    c.setStrokeColorRGB(0.5, 0.5, 0.5)
                    c.setLineWidth(config['border_width'])
                    c.rect(x_base, y_base, slide_width, slide_height)
                
                # Desenha a imagem
                c.drawImage(
                    ImageReader(img_buffer),
                    x_final,
                    y_final,
                    width=draw_width,
                    height=draw_height,
                    preserveAspectRatio=True,
                    mask='auto'
                )
                
                # Adiciona numeração se habilitado
                if config['show_numbers']:
                    c.setFont("Helvetica", config['number_size'])
                    c.setFillColorRGB(0.3, 0.3, 0.3)
                    number_text = f"{page_idx + j + 1}"
                    
                    if config['number_position'] == 'Superior Esquerdo':
                        c.drawString(x_base + 5, y_base + slide_height - config['number_size'] - 5, number_text)
                    elif config['number_position'] == 'Superior Direito':
                        c.drawString(x_base + slide_width - 20, y_base + slide_height - config['number_size'] - 5, number_text)
                    elif config['number_position'] == 'Inferior Esquerdo':
                        c.drawString(x_base + 5, y_base + 5, number_text)
                    elif config['number_position'] == 'Inferior Direito':
                        c.drawString(x_base + slide_width - 20, y_base + 5, number_text)
                    else:  # Centro
                        c.drawString(x_base + slide_width/2 - 10, y_base + slide_height/2, number_text)
        
        # Nova página se houver mais slides
        if page_idx + slides_per_page < len(selected_images):
            c.showPage()
    
    # Salva o PDF
    c.save()

# Interface principal do Streamlit
def main():
    st.title("📄 Otimizador de Slides PDF")
    st.markdown("""
    Este aplicativo permite otimizar a impressão de slides de apresentações em PDF,
    organizando múltiplos slides por página para economizar papel.
    """)
    
    # Verifica se o poppler está instalado
    if not check_poppler():
        st.stop()
    
    # Inicializa configurações padrão no session_state
    if 'config' not in st.session_state:
        st.session_state.config = {
            'page_size': 'A4',
            'page_orientation': 'Paisagem',
            'grid_cols': 2,
            'grid_rows': 2,
            'margin_left': 3.0,
            'margin_right': 1.0,
            'margin_top': 1.0,
            'margin_bottom': 1.0,
            'spacing': 20,
            'show_borders': False,
            'border_width': 0.5,
            'show_numbers': False,
            'number_size': 10,
            'number_position': 'Inferior Esquerdo',
            'image_quality': 'Alta',
            'rotate_images': 0,
            'image_orientation': 'Manter Original',
            'fit_mode': 'Ajustar (manter visível)'
        }
    
    # Upload do arquivo PDF
    uploaded_file = st.file_uploader(
        "Escolha um arquivo PDF",
        type=['pdf'],
        help="Selecione o arquivo PDF que contém os slides"
    )
    
    if uploaded_file is not None:
        # Salva o arquivo temporariamente
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = tmp_file.name
        
        try:
            # Converte PDF em imagens
            with st.spinner("Processando PDF... Isso pode levar alguns segundos."):
                images = pdf_to_images(tmp_path)
            
            if images:
                st.success(f"✅ PDF carregado com sucesso! Total de {len(images)} páginas.")
                
                # Layout em duas colunas principais
                col_main, col_preview = st.columns([2, 1])
                
                with col_main:
                    # Seção de opções avançadas
                    with st.expander("⚙️ Opções Avançadas", expanded=False):
                        tab1, tab2, tab3, tab4 = st.tabs(["📐 Layout", "📏 Margens", "🎨 Aparência", "🖼️ Imagens"])
                        
                        with tab1:
                            col1, col2 = st.columns(2)
                            with col1:
                                st.session_state.config['page_size'] = st.selectbox(
                                    "Tamanho do Papel",
                                    options=list(PAGE_SIZES.keys()),
                                    index=list(PAGE_SIZES.keys()).index(st.session_state.config['page_size'])
                                )
                                
                                st.session_state.config['page_orientation'] = st.radio(
                                    "Orientação da Página",
                                    options=['Paisagem', 'Retrato'],
                                    index=0 if st.session_state.config['page_orientation'] == 'Paisagem' else 1
                                )
                            
                            with col2:
                                st.session_state.config['grid_cols'] = st.number_input(
                                    "Colunas no Grid",
                                    min_value=1,
                                    max_value=6,
                                    value=st.session_state.config['grid_cols']
                                )
                                
                                st.session_state.config['grid_rows'] = st.number_input(
                                    "Linhas no Grid",
                                    min_value=1,
                                    max_value=6,
                                    value=st.session_state.config['grid_rows']
                                )
                            
                            total_slides = st.session_state.config['grid_cols'] * st.session_state.config['grid_rows']
                            st.info(f"💡 Total de {total_slides} slides por página")
                        
                        with tab2:
                            col1, col2 = st.columns(2)
                            with col1:
                                st.session_state.config['margin_left'] = st.number_input(
                                    "Margem Esquerda (cm)",
                                    min_value=0.0,
                                    max_value=10.0,
                                    value=st.session_state.config['margin_left'],
                                    step=0.5,
                                    help="Recomendado: 3cm para fichário"
                                )
                                
                                st.session_state.config['margin_right'] = st.number_input(
                                    "Margem Direita (cm)",
                                    min_value=0.0,
                                    max_value=10.0,
                                    value=st.session_state.config['margin_right'],
                                    step=0.5
                                )
                            
                            with col2:
                                st.session_state.config['margin_top'] = st.number_input(
                                    "Margem Superior (cm)",
                                    min_value=0.0,
                                    max_value=10.0,
                                    value=st.session_state.config['margin_top'],
                                    step=0.5
                                )
                                
                                st.session_state.config['margin_bottom'] = st.number_input(
                                    "Margem Inferior (cm)",
                                    min_value=0.0,
                                    max_value=10.0,
                                    value=st.session_state.config['margin_bottom'],
                                    step=0.5
                                )
                            
                            st.session_state.config['spacing'] = st.slider(
                                "Espaçamento entre Slides (pixels)",
                                min_value=0,
                                max_value=50,
                                value=st.session_state.config['spacing']
                            )
                        
                        with tab3:
                            col1, col2 = st.columns(2)
                            with col1:
                                st.session_state.config['show_borders'] = st.checkbox(
                                    "Mostrar Bordas",
                                    value=st.session_state.config['show_borders']
                                )
                                
                                if st.session_state.config['show_borders']:
                                    st.session_state.config['border_width'] = st.slider(
                                        "Espessura da Borda",
                                        min_value=0.1,
                                        max_value=3.0,
                                        value=st.session_state.config['border_width'],
                                        step=0.1
                                    )
                                
                                st.session_state.config['show_numbers'] = st.checkbox(
                                    "Mostrar Numeração",
                                    value=st.session_state.config['show_numbers']
                                )
                            
                            with col2:
                                if st.session_state.config['show_numbers']:
                                    st.session_state.config['number_size'] = st.slider(
                                        "Tamanho da Numeração",
                                        min_value=6,
                                        max_value=20,
                                        value=st.session_state.config['number_size']
                                    )
                                    
                                    st.session_state.config['number_position'] = st.selectbox(
                                        "Posição da Numeração",
                                        options=['Superior Esquerdo', 'Superior Direito', 
                                               'Inferior Esquerdo', 'Inferior Direito', 'Centro'],
                                        index=2
                                    )
                        
                        with tab4:
                            col1, col2 = st.columns(2)
                            with col1:
                                st.session_state.config['image_quality'] = st.select_slider(
                                    "Qualidade da Imagem",
                                    options=['Baixa', 'Média', 'Alta'],
                                    value=st.session_state.config['image_quality']
                                )
                                
                                st.session_state.config['rotate_images'] = st.slider(
                                    "Rotação das Imagens (graus)",
                                    min_value=0,
                                    max_value=270,
                                    value=st.session_state.config['rotate_images'],
                                    step=90
                                )
                            
                            with col2:
                                st.session_state.config['image_orientation'] = st.selectbox(
                                    "Orientação das Imagens",
                                    options=['Manter Original', 'Forçar Paisagem', 'Forçar Retrato'],
                                    index=0
                                )
                                
                                st.session_state.config['fit_mode'] = st.radio(
                                    "Modo de Ajuste",
                                    options=['Ajustar (manter visível)', 'Preencher (pode cortar)'],
                                    index=0
                                )
                    
                    # Seção de seleção de páginas
                    st.markdown("### 📑 Selecione as páginas para incluir no PDF otimizado")
                    
                    # Botões de seleção rápida
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        if st.button("✅ Selecionar Todas"):
                            st.session_state.selected_pages = list(range(len(images)))
                    with col2:
                        if st.button("❌ Desmarcar Todas"):
                            st.session_state.selected_pages = []
                    with col3:
                        if st.button("🔄 Inverter Seleção"):
                            current = st.session_state.get('selected_pages', [])
                            st.session_state.selected_pages = [i for i in range(len(images)) if i not in current]
                    with col4:
                        if st.button("📊 Páginas Pares"):
                            st.session_state.selected_pages = [i for i in range(len(images)) if (i + 1) % 2 == 0]
                    
                    # Inicializa a seleção se não existir
                    if 'selected_pages' not in st.session_state:
                        st.session_state.selected_pages = list(range(len(images)))
                    
                    # Grade de visualização com checkboxes
                    cols_per_row = 4
                    rows = (len(images) + cols_per_row - 1) // cols_per_row
                    
                    selected_indices = []
                    
                    for row in range(rows):
                        cols = st.columns(cols_per_row)
                        for col_idx in range(cols_per_row):
                            page_idx = row * cols_per_row + col_idx
                            if page_idx < len(images):
                                with cols[col_idx]:
                                    # Redimensiona a imagem para visualização
                                    img = images[page_idx]
                                    img_resized = img.copy()
                                    img_resized.thumbnail((300, 300), Image.Resampling.LANCZOS)
                                    
                                    # Mostra a imagem
                                    st.image(img_resized, use_container_width=True)
                                    
                                    # Checkbox para seleção
                                    is_selected = st.checkbox(
                                        f"Página {page_idx + 1}",
                                        value=page_idx in st.session_state.selected_pages,
                                        key=f"page_{page_idx}"
                                    )
                                    
                                    if is_selected:
                                        selected_indices.append(page_idx)
                    
                    # Atualiza as páginas selecionadas
                    st.session_state.selected_pages = selected_indices
                    
                    # Mostra contador de páginas selecionadas
                    st.info(f"📊 {len(selected_indices)} páginas selecionadas de {len(images)} total")
                
                with col_preview:
                    st.markdown("### 👁️ Preview do Layout")
                    
                    # Cria e mostra o preview
                    preview_img = create_layout_preview(st.session_state.config)
                    st.image(preview_img, use_container_width=True)
                    
                    # Informações sobre o layout
                    total_slides_per_page = st.session_state.config['grid_cols'] * st.session_state.config['grid_rows']
                    if selected_indices:
                        total_pages_optimized = (len(selected_indices) + total_slides_per_page - 1) // total_slides_per_page
                        economia = ((len(selected_indices) - total_pages_optimized) / len(selected_indices) * 100) if len(selected_indices) > 0 else 0
                        
                        st.markdown("#### 📊 Estatísticas")
                        st.write(f"- Slides selecionados: {len(selected_indices)}")
                        st.write(f"- Páginas no PDF final: {total_pages_optimized}")
                        st.write(f"- Slides por página: {total_slides_per_page}")
                        st.write(f"- Economia de papel: {economia:.1f}%")
                
                # Botão para gerar PDF otimizado
                if st.button("🚀 Gerar PDF Otimizado", type="primary", disabled=len(selected_indices) == 0):
                    if selected_indices:
                        with st.spinner("Gerando PDF otimizado..."):
                            # Filtra apenas as imagens selecionadas
                            selected_images = [images[i] for i in sorted(selected_indices)]
                            
                            # Cria o PDF otimizado
                            output_path = tempfile.mktemp(suffix='.pdf')
                            create_optimized_pdf(selected_images, output_path, st.session_state.config)
                            
                            # Lê o arquivo gerado
                            with open(output_path, 'rb') as f:
                                pdf_data = f.read()
                            
                            # Calcula estatísticas
                            total_pages_original = len(selected_indices)
                            total_pages_optimized = (total_pages_original + total_slides_per_page - 1) // total_slides_per_page
                            
                            st.success(f"""
                            ✅ PDF otimizado gerado com sucesso!
                            - Páginas originais selecionadas: {total_pages_original}
                            - Páginas no PDF otimizado: {total_pages_optimized}
                            - Slides por página: {total_slides_per_page} (grid {st.session_state.config['grid_cols']}x{st.session_state.config['grid_rows']})
                            - Economia de papel: {((total_pages_original - total_pages_optimized) / total_pages_original * 100):.1f}%
                            """)
                            
                            # Botão de download
                            st.download_button(
                                label="📥 Baixar PDF Otimizado",
                                data=pdf_data,
                                file_name=f"slides_otimizados_{uploaded_file.name}",
                                mime="application/pdf"
                            )
                            
                            # Limpa o arquivo temporário
                            os.unlink(output_path)
                    else:
                        st.warning("⚠️ Por favor, selecione pelo menos uma página.")
                
        except Exception as e:
            st.error(f"❌ Erro ao processar o PDF: {str(e)}")
            st.info("Verifique se o arquivo PDF não está corrompido e tente novamente.")
        
        finally:
            # Limpa o arquivo temporário
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    # Instruções de uso
    with st.expander("ℹ️ Como usar este aplicativo"):
        st.markdown("""
        1. **Faça upload do seu PDF** usando o botão acima
        2. **Configure o layout** nas Opções Avançadas (opcional)
        3. **Visualize o preview** do layout em tempo real
        4. **Selecione as páginas** que deseja incluir no PDF otimizado
        5. **Clique em "Gerar PDF Otimizado"** para criar o novo arquivo
        6. **Baixe o PDF** com múltiplos slides por página
        
        **Recursos Avançados:**
        - **Layout flexível**: Configure quantos slides por página (1x1 até 6x6)
        - **Margens personalizadas**: Ajuste cada margem individualmente
        - **Orientação**: Escolha entre paisagem ou retrato
        - **Aparência**: Adicione bordas, numeração, ajuste qualidade
        - **Rotação**: Gire imagens em 90°, 180° ou 270°
        - **Preview em tempo real**: Veja como ficará antes de gerar
        
        **Dicas:**
        - Para fichário, use margem esquerda de 3cm
        - Grid 2x2 é ideal para slides de apresentação
        - Grid 3x2 ou 2x3 funciona bem para documentos
        - Use bordas para melhor visualização na impressão
        """)

if __name__ == "__main__":
    main()