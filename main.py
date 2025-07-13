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
from reportlab.lib.colors import Color, HexColor
import pdf2image
import subprocess
import platform
import math
import copy
from datetime import datetime
import json

# Configuração da página do Streamlit
st.set_page_config(
    page_title="Otimizador de Slides PDF - Multi-arquivo",
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

# Templates predefinidos
TEMPLATES = {
    "Padrão (2x2)": {
        'grid_cols': 2, 'grid_rows': 2,
        'margin_left': 3.0, 'margin_right': 1.0,
        'margin_top': 1.0, 'margin_bottom': 1.0,
        'page_orientation': 'Paisagem'
    },
    "Econômico (3x3)": {
        'grid_cols': 3, 'grid_rows': 3,
        'margin_left': 1.0, 'margin_right': 0.5,
        'margin_top': 0.5, 'margin_bottom': 0.5,
        'page_orientation': 'Paisagem'
    },
    "Revisão Rápida (4x4)": {
        'grid_cols': 4, 'grid_rows': 4,
        'margin_left': 1.0, 'margin_right': 0.5,
        'margin_top': 0.5, 'margin_bottom': 0.5,
        'page_orientation': 'Paisagem',
        'show_numbers': True,
        'number_size': 8
    },
    "Anotações (1x2)": {
        'grid_cols': 1, 'grid_rows': 2,
        'margin_left': 5.0, 'margin_right': 3.0,
        'margin_top': 2.0, 'margin_bottom': 2.0,
        'page_orientation': 'Retrato',
        'show_borders': True
    },
    "Apresentação (1x1)": {
        'grid_cols': 1, 'grid_rows': 1,
        'margin_left': 2.0, 'margin_right': 2.0,
        'margin_top': 2.0, 'margin_bottom': 2.0,
        'page_orientation': 'Paisagem'
    },
    "Handout (2x3)": {
        'grid_cols': 2, 'grid_rows': 3,
        'margin_left': 2.0, 'margin_right': 2.0,
        'margin_top': 2.0, 'margin_bottom': 2.0,
        'page_orientation': 'Retrato',
        'spacing': 15
    }
}

# Função para verificar e instalar poppler se necessário
def check_poppler():
    """Verifica se o poppler está instalado e tenta instalar se necessário."""
    # Lista de comandos do poppler para verificar
    poppler_commands = ['pdfinfo', 'pdfimages', 'pdftoppm', 'pdftocairo']
    
    # Verifica primeiro se há um caminho customizado
    custom_path = st.session_state.get('poppler_path', None)
    if custom_path and os.path.exists(custom_path):
        for cmd in poppler_commands:
            try:
                full_cmd = os.path.join(custom_path, cmd)
                if platform.system() == "Windows":
                    full_cmd += ".exe"
                
                if os.path.exists(full_cmd):
                    st.success(f"✅ Poppler encontrado no caminho customizado: {custom_path}")
                    return True
            except:
                continue
    
    # Locais comuns onde o poppler pode estar instalado
    common_paths = []
    if platform.system() == "Windows":
        common_paths = [
            r"C:\Program Files\poppler\Library\bin",
            r"C:\Program Files (x86)\poppler\Library\bin",
            r"C:\poppler\Library\bin",
            r"C:\msys64\mingw64\bin",
            r"C:\tools\poppler\Library\bin"
        ]
    elif platform.system() == "Darwin":  # macOS
        common_paths = [
            "/usr/local/bin",
            "/opt/homebrew/bin",
            "/opt/local/bin",
            "/usr/bin"
        ]
    else:  # Linux
        common_paths = [
            "/usr/bin",
            "/usr/local/bin",
            "/snap/bin"
        ]
    
    # Primeiro tenta no PATH padrão
    for cmd in poppler_commands:
        try:
            if platform.system() == "Windows":
                result = subprocess.run([f'{cmd}.exe', '-v'], capture_output=True, text=True, shell=True)
            else:
                result = subprocess.run([cmd, '-v'], capture_output=True, text=True)
            
            if result.returncode == 0 or 'version' in result.stdout.lower() or 'version' in result.stderr.lower():
                # Poppler está no PATH padrão - não precisa de mensagem extra
                return True
        except (FileNotFoundError, subprocess.SubprocessError):
            continue
    
    # Tenta nos caminhos comuns
    for path in common_paths:
        for cmd in poppler_commands:
            try:
                full_cmd = os.path.join(path, cmd)
                if platform.system() == "Windows":
                    full_cmd += ".exe"
                
                if os.path.exists(full_cmd):
                    result = subprocess.run([full_cmd, '-v'], capture_output=True, text=True)
                    if result.returncode == 0 or 'version' in result.stdout.lower() or 'version' in result.stderr.lower():
                        st.info(f"✅ Poppler encontrado em: {path}")
                        st.session_state.poppler_path = path  # Salva o caminho automaticamente
                        return True
            except:
                continue
    
    # Se chegou aqui, poppler não está instalado ou não está no PATH
    st.warning("⚠️ Poppler não encontrado no sistema.")
    
    # Detecta o sistema operacional
    system = platform.system()
    
    if system == "Windows":
        st.info("""
        **Para Windows:**
        1. Baixe o Poppler: https://github.com/oschwartz10612/poppler-windows/releases/
        2. Extraia em uma pasta (ex: C:\\poppler)
        3. Adicione o caminho bin ao PATH do sistema (ex: C:\\poppler\\Library\\bin)
        4. Reinicie o terminal/IDE e tente novamente
        
        **Ou use a configuração avançada nas Configurações Globais para especificar o caminho**
        """)
        return False
    
    try:
        if system == "Darwin":  # macOS
            # Verifica se o homebrew está instalado
            result = subprocess.run(["brew", "--version"], capture_output=True)
            if result.returncode != 0:
                st.error("❌ Homebrew não encontrado. Instale primeiro: https://brew.sh")
                return False
            
            # Instala poppler via homebrew
            st.info("📦 Instalando Poppler via Homebrew...")
            result = subprocess.run(["brew", "install", "poppler"], capture_output=True, text=True)
            if result.returncode == 0:
                st.success("✅ Poppler instalado com sucesso!")
                return True
            else:
                st.error("❌ Erro ao instalar Poppler via Homebrew")
                st.code(result.stderr)
                return False
                
        elif system == "Linux":
            st.info("📦 Tentando instalar Poppler...")
            # Para sistemas baseados em Debian/Ubuntu
            result = subprocess.run(["sudo", "apt-get", "update"], capture_output=True)
            if result.returncode == 0:
                result = subprocess.run(["sudo", "apt-get", "install", "-y", "poppler-utils"], capture_output=True)
                if result.returncode == 0:
                    st.success("✅ Poppler instalado com sucesso!")
                    return True
            
            # Se falhou, tenta com outras distros
            st.error("❌ Não foi possível instalar automaticamente.")
            st.info("""
            **Instale manualmente:**
            - Ubuntu/Debian: `sudo apt-get install poppler-utils`
            - Fedora: `sudo dnf install poppler-utils`
            - Arch: `sudo pacman -S poppler`
            - CentOS/RHEL: `sudo yum install poppler-utils`
            """)
            return False
            
    except Exception as e:
        st.error(f"❌ Erro ao tentar instalar Poppler: {str(e)}")
        return False

# Função para converter páginas PDF em imagens
def pdf_to_images(pdf_path, dpi=150):
    """Converte todas as páginas de um PDF em imagens."""
    try:
        # Configurações para pdf2image
        kwargs = {
            'dpi': dpi,
            'fmt': 'png',
            'thread_count': 4,
            'use_pdftocairo': True
        }
        
        # Se houver um caminho customizado do poppler, usa ele
        poppler_path = st.session_state.get('poppler_path', None)
        if poppler_path and os.path.exists(poppler_path):
            kwargs['poppler_path'] = poppler_path
        
        # Tenta converter com as configurações
        images = pdf2image.convert_from_path(pdf_path, **kwargs)
        return images
    except Exception as e:
        # Tenta com configurações mais básicas se falhar
        try:
            kwargs_basic = {'dpi': dpi}
            poppler_path = st.session_state.get('poppler_path', None)
            if poppler_path and os.path.exists(poppler_path):
                kwargs_basic['poppler_path'] = poppler_path
                
            images = pdf2image.convert_from_path(pdf_path, **kwargs_basic)
            return images
        except Exception as e2:
            st.error(f"Erro ao converter PDF em imagens: {str(e2)}")
            st.info("Verifique se o Poppler está instalado corretamente")
            return None

# Função para criar configuração padrão
def get_default_config():
    return {
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
        'fit_mode': 'Ajustar (manter visível)',
        'watermark_text': '',
        'watermark_size': 40,
        'watermark_opacity': 0.1,
        'header_text': '',
        'footer_text': '',
        'header_footer_size': 10
    }

# Função para criar preview do layout
def create_layout_preview(config, selected_count=4, page_number=1):
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
    
    # Verifica se esta página será rotacionada
    landscape_binder_mode = st.session_state.get('landscape_binder_mode', False)
    is_rotated = landscape_binder_mode and (page_number % 2 == 0)
    
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
    
    # Desenha fundo e área de margens
    draw.rectangle([0, 0, preview_width, preview_height], fill='#f0f0f0')
    draw.rectangle([margin_left, margin_top, preview_width - margin_right, preview_height - margin_bottom], fill='white')
    
    # Configurações do grid
    cols = max(1, config['grid_cols'])  # Garante pelo menos 1
    rows = max(1, config['grid_rows'])  # Garante pelo menos 1
    
    # Verifica se há espaço suficiente
    if usable_width > 10 and usable_height > 10 and cols > 0 and rows > 0:
        # Calcula tamanho de cada slide
        slide_width = max(1, (usable_width - (cols - 1) * spacing) / cols)
        slide_height = max(1, (usable_height - (rows - 1) * spacing) / rows)
        
        # Desenha marca d'água se configurada
        if config.get('watermark_text', ''):
            # Texto da marca d'água
            watermark = config['watermark_text']
            # Desenha no centro em cinza claro
            text_x = preview_width // 2
            text_y = preview_height // 2
            draw.text((text_x, text_y), watermark, 
                     fill=(220, 220, 220), anchor="mm")
        
        # Desenha cabeçalho se configurado
        if config.get('header_text', ''):
            draw.text((margin_left + 5, margin_top - 15), config['header_text'], 
                     fill='#333333')
        
        # Desenha os slides
        slide_num = 1
        slides_per_page = cols * rows
        for row in range(rows):
            for col in range(cols):
                if slide_num <= min(selected_count, slides_per_page):
                    x = margin_left + col * (slide_width + spacing)
                    y = margin_top + row * (slide_height + spacing)
                    
                    # Garante que as coordenadas são válidas
                    x2 = min(x + slide_width, preview_width - margin_right)
                    y2 = min(y + slide_height, preview_height - margin_bottom)
                    
                    # Desenha retângulo do slide
                    if config['show_borders']:
                        draw.rectangle([x, y, x2, y2], 
                                     fill='white', outline='#666666', width=2)
                    else:
                        draw.rectangle([x, y, x2, y2], 
                                     fill='white', outline='#e0e0e0', width=1)
                    
                    # Adiciona número do slide no centro
                    text = f"{slide_num}"
                    text_color = '#666666'
                    
                    # Posição central do texto
                    text_x = x + slide_width / 2
                    text_y = y + slide_height / 2
                    
                    # Se estiver rotacionado, adiciona indicador
                    if is_rotated:
                        # Rotaciona o texto 180°
                        rotated_img = Image.new('RGBA', (int(slide_width), int(slide_height)), (255, 255, 255, 0))
                        rotated_draw = ImageDraw.Draw(rotated_img)
                        rotated_draw.text((slide_width/2, slide_height/2), text, 
                                        fill=text_color, anchor="mm")
                        rotated_img = rotated_img.rotate(180)
                        img.paste(rotated_img, (int(x), int(y)), rotated_img)
                    else:
                        # Desenha o número normalmente
                        draw.text((text_x, text_y), text, fill=text_color, anchor="mm")
                
                slide_num += 1
        
        # Desenha rodapé se configurado
        if config.get('footer_text', ''):
            draw.text((margin_left + 5, preview_height - margin_bottom + 5), 
                     config['footer_text'], fill='#333333')
        
        # Indicador de rotação se ativo
        if is_rotated:
            # Adiciona símbolo de rotação no canto
            draw.text((preview_width - 50, 10), "🔄 180°", fill='#ff6666')
    else:
        # Se não há espaço suficiente, mostra mensagem
        msg = "Margens muito grandes\npara visualizar"
        draw.multiline_text((preview_width // 2, preview_height // 2), 
                           msg, fill='#ff0000', anchor="mm", align="center")
    
    # Linha tracejada na margem esquerda para fichário
    if config['margin_left'] >= 2.5:  # Se margem >= 2.5cm
        # Desenha furos de fichário
        hole_y_positions = [
            preview_height * 0.2,
            preview_height * 0.5,
            preview_height * 0.8
        ]
        hole_x = margin_left - 15
        
        for y_pos in hole_y_positions:
            # Desenha círculo representando furo
            draw.ellipse([hole_x - 5, y_pos - 5, hole_x + 5, y_pos + 5], 
                        outline='#ff6666', width=2)
    
    return img

# Função para criar página em branco
def create_blank_page_image(width=595, height=842):
    """Cria uma imagem de página em branco."""
    img = Image.new('RGB', (int(width), int(height)), 'white')
    draw = ImageDraw.Draw(img)
    
    # Adiciona linhas pautadas opcionalmente
    if st.session_state.get('blank_pages_lined', False):
        line_spacing = 30
        margin = 50
        for y in range(margin + line_spacing, int(height) - margin, line_spacing):
            draw.line([(margin, y), (int(width) - margin, y)], fill='#e0e0e0', width=1)
    
    return img

# Função para criar o PDF otimizado com grupos
def create_optimized_pdf_with_groups(groups, all_images_dict, output_path):
    """
    Cria um PDF com múltiplos slides por página baseado nos grupos e suas configurações.
    """
    # Configurações globais
    global_watermark = st.session_state.get('global_watermark', '')
    global_page_numbers = st.session_state.get('global_page_numbers', False)
    landscape_binder_mode = st.session_state.get('landscape_binder_mode', False)
    
    # Cria o canvas do PDF
    first_group = groups[0]
    page_size = PAGE_SIZES[first_group['config']['page_size']]
    
    if first_group['config']['page_orientation'] == 'Paisagem':
        c = canvas.Canvas(output_path, pagesize=landscape(page_size))
    else:
        c = canvas.Canvas(output_path, pagesize=portrait(page_size))
    
    first_page = True
    global_page_num = 1
    
    # Processa cada grupo
    for group_idx, group in enumerate(groups):
        config = group['config']
        selected_pages = group['pages']  # Lista de tuplas (pdf_index, page_index)
        
        if not selected_pages:
            continue
        
        # Obtém as imagens selecionadas para este grupo
        selected_images = []
        for pdf_idx, page_idx in selected_pages:
            if pdf_idx == -1:  # Página em branco
                selected_images.append(create_blank_page_image())
            else:
                selected_images.append(all_images_dict[pdf_idx][page_idx])
        
        # Configurações do grupo
        page_size = PAGE_SIZES[config['page_size']]
        
        if config['page_orientation'] == 'Paisagem':
            page_width, page_height = landscape(page_size)
        else:
            page_width, page_height = portrait(page_size)
        
        margin_left = config['margin_left'] * 28.35
        margin_right = config['margin_right'] * 28.35
        margin_top = config['margin_top'] * 28.35
        margin_bottom = config['margin_bottom'] * 28.35
        spacing = config['spacing']
        
        cols = config['grid_cols']
        rows = config['grid_rows']
        slides_per_page = cols * rows
        
        slide_width = (page_width - margin_left - margin_right - (cols - 1) * spacing) / cols
        slide_height = (page_height - margin_top - margin_bottom - (rows - 1) * spacing) / rows
        
        # Processa as imagens do grupo
        for page_idx in range(0, len(selected_images), slides_per_page):
            if not first_page:
                c.showPage()
                global_page_num += 1
                if config['page_orientation'] == 'Paisagem':
                    c.setPageSize(landscape(page_size))
                else:
                    c.setPageSize(portrait(page_size))
            else:
                first_page = False
            
            # Verifica se deve rotacionar a página (modo fichário paisagem)
            should_rotate = landscape_binder_mode and (global_page_num % 2 == 0)
            
            if should_rotate:
                # Salva o estado atual e rotaciona 180°
                c.saveState()
                c.translate(page_width/2, page_height/2)
                c.rotate(180)
                c.translate(-page_width/2, -page_height/2)
            
            # Adiciona marca d'água global ou do grupo
            watermark = config.get('watermark_text', '') or global_watermark
            if watermark:
                c.saveState()
                c.setFont("Helvetica", config.get('watermark_size', 40))
                c.setFillColor(Color(0, 0, 0, alpha=config.get('watermark_opacity', 0.1)))
                c.translate(page_width/2, page_height/2)
                c.rotate(45)
                c.drawCentredString(0, 0, watermark)
                c.restoreState()
            
            # Adiciona cabeçalho
            if config.get('header_text'):
                c.setFont("Helvetica", config.get('header_footer_size', 10))
                c.setFillColorRGB(0.2, 0.2, 0.2)
                header = config['header_text'].replace('{page}', str(global_page_num))
                header = header.replace('{date}', datetime.now().strftime('%d/%m/%Y'))
                header = header.replace('{group}', group['name'])
                c.drawString(margin_left, page_height - 20, header)
            
            # Adiciona rodapé
            if config.get('footer_text'):
                c.setFont("Helvetica", config.get('header_footer_size', 10))
                c.setFillColorRGB(0.2, 0.2, 0.2)
                footer = config['footer_text'].replace('{page}', str(global_page_num))
                footer = footer.replace('{date}', datetime.now().strftime('%d/%m/%Y'))
                footer = footer.replace('{group}', group['name'])
                c.drawString(margin_left, 20, footer)
            
            # Adiciona numeração global de página
            if global_page_numbers:
                c.setFont("Helvetica", 10)
                c.setFillColorRGB(0.5, 0.5, 0.5)
                c.drawRightString(page_width - 20, 20, f"Página {global_page_num}")
            
            # Calcula posições dos slides no grid
            positions = []
            for row in range(rows):
                for col in range(cols):
                    x = margin_left + col * (slide_width + spacing)
                    y = page_height - margin_top - (row + 1) * slide_height - row * spacing
                    positions.append((x, y))
            
            # Adiciona slides na página atual
            for j in range(slides_per_page):
                if page_idx + j < len(selected_images):
                    img = selected_images[page_idx + j]
                    
                    # Número da página original
                    pdf_idx, orig_page_idx = selected_pages[page_idx + j]
                    if pdf_idx >= 0:
                        original_page_num = orig_page_idx + 1
                    else:
                        original_page_num = "Branco"
                    
                    if config['rotate_images'] != 0:
                        img = img.rotate(-config['rotate_images'], expand=True)
                    
                    img_buffer = io.BytesIO()
                    if config['image_quality'] == 'Alta':
                        quality = 95
                    elif config['image_quality'] == 'Média':
                        quality = 85
                    else:
                        quality = 70
                    
                    img.save(img_buffer, format='PNG', optimize=True, quality=quality)
                    img_buffer.seek(0)
                    
                    img_width, img_height = img.size
                    aspect_ratio = img_width / img_height
                    
                    if config['image_orientation'] == 'Forçar Paisagem' and aspect_ratio < 1:
                        img = img.rotate(90, expand=True)
                        img_buffer = io.BytesIO()
                        img.save(img_buffer, format='PNG', optimize=True, quality=quality)
                        img_buffer.seek(0)
                        img_width, img_height = img_height, img_width
                        aspect_ratio = img_width / img_height
                    elif config['image_orientation'] == 'Forçar Retrato' and aspect_ratio > 1:
                        img = img.rotate(90, expand=True)
                        img_buffer = io.BytesIO()
                        img.save(img_buffer, format='PNG', optimize=True, quality=quality)
                        img_buffer.seek(0)
                        img_width, img_height = img_height, img_width
                        aspect_ratio = img_width / img_height
                    
                    if config['fit_mode'] == 'Preencher (pode cortar)':
                        if aspect_ratio > slide_width / slide_height:
                            draw_height = slide_height
                            draw_width = slide_height * aspect_ratio
                        else:
                            draw_width = slide_width
                            draw_height = slide_width / aspect_ratio
                    else:
                        if aspect_ratio > slide_width / slide_height:
                            draw_width = slide_width
                            draw_height = slide_width / aspect_ratio
                        else:
                            draw_height = slide_height
                            draw_width = slide_height * aspect_ratio
                    
                    x_offset = (slide_width - draw_width) / 2
                    y_offset = (slide_height - draw_height) / 2
                    
                    x_base, y_base = positions[j]
                    
                    x_final = x_base + x_offset
                    y_final = y_base + y_offset
                    
                    if config['show_borders']:
                        c.setStrokeColorRGB(0.5, 0.5, 0.5)
                        c.setLineWidth(config['border_width'])
                        c.rect(x_base, y_base, slide_width, slide_height)
                    
                    c.drawImage(
                        ImageReader(img_buffer),
                        x_final,
                        y_final,
                        width=draw_width,
                        height=draw_height,
                        preserveAspectRatio=True,
                        mask='auto'
                    )
                    
                    if config['show_numbers'] and pdf_idx >= 0:
                        c.setFont("Helvetica", config['number_size'])
                        c.setFillColorRGB(0.3, 0.3, 0.3)
                        
                        # Mostra nome do PDF se houver múltiplos
                        if len(st.session_state.get('pdf_files', [])) > 1:
                            pdf_name = st.session_state['pdf_names'][pdf_idx]
                            number_text = f"{pdf_name[:10]}... p{original_page_num}"
                        else:
                            number_text = f"{original_page_num}"
                        
                        if config['number_position'] == 'Superior Esquerdo':
                            c.drawString(x_base + 5, y_base + slide_height - config['number_size'] - 5, number_text)
                        elif config['number_position'] == 'Superior Direito':
                            c.drawString(x_base + slide_width - 20, y_base + slide_height - config['number_size'] - 5, number_text)
                        elif config['number_position'] == 'Inferior Esquerdo':
                            c.drawString(x_base + 5, y_base + 5, number_text)
                        elif config['number_position'] == 'Inferior Direito':
                            c.drawString(x_base + slide_width - 20, y_base + 5, number_text)
                        else:
                            c.drawString(x_base + slide_width/2 - 10, y_base + slide_height/2, number_text)
            
            # Restaura o estado se a página foi rotacionada
            if should_rotate:
                c.restoreState()
    
    c.save()

# Interface principal do Streamlit
def main():
    st.title("📄 Otimizador de Slides PDF - Multi-arquivo")
    st.markdown("""
    Organize slides de **múltiplos PDFs** em um único arquivo otimizado para impressão.
    Configure grupos independentes, adicione páginas em branco, marca d'água e muito mais!
    """)
    
    # Verifica poppler no início (mas não bloqueia se falhar)
    if 'poppler_ok' not in st.session_state:
        with st.spinner("Verificando dependências..."):
            st.session_state.poppler_ok = check_poppler()
    
    poppler_ok = st.session_state.poppler_ok
    
    if poppler_ok:
        st.success("✅ Sistema pronto para processar PDFs", icon="✅")
    else:
        st.warning("""
        ⚠️ **Poppler não detectado no PATH**
        
        O aplicativo precisa do Poppler para converter PDFs em imagens.
        Por favor, instale-o seguindo as instruções acima e recarregue a página.
        """)
        # Botão para verificar novamente
        if st.button("🔄 Verificar novamente"):
            st.session_state.poppler_ok = check_poppler()
            st.rerun()
    
    # Inicializa session_state
    if 'groups' not in st.session_state:
        st.session_state.groups = [{
            'name': 'Grupo 1',
            'pages': [],
            'config': get_default_config()
        }]
    
    if 'current_group' not in st.session_state:
        st.session_state.current_group = 0
    
    if 'pdf_files' not in st.session_state:
        st.session_state.pdf_files = []
    
    if 'all_images' not in st.session_state:
        st.session_state.all_images = {}
    
    if 'pdf_names' not in st.session_state:
        st.session_state.pdf_names = []
    
    # Upload de múltiplos arquivos PDF
    uploaded_files = st.file_uploader(
        "Escolha um ou mais arquivos PDF",
        type=['pdf'],
        accept_multiple_files=True,
        help="Você pode selecionar múltiplos PDFs segurando Ctrl/Cmd"
    )
    
    if uploaded_files:
        # Verifica poppler novamente antes de processar
        if not st.session_state.get('poppler_ok', False):
            st.error("❌ Por favor, instale o Poppler antes de processar PDFs.")
            st.stop()
        
        # Processa novos arquivos
        new_files = []
        for uploaded_file in uploaded_files:
            if uploaded_file.name not in st.session_state.pdf_names:
                new_files.append(uploaded_file)
        
        if new_files:
            with st.spinner(f"Processando {len(new_files)} novo(s) PDF(s)..."):
                for uploaded_file in new_files:
                    # Salva o arquivo temporariamente
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                        tmp_file.write(uploaded_file.getvalue())
                        tmp_path = tmp_file.name
                    
                    # Converte em imagens
                    dpi = st.session_state.get('pdf_dpi', 150)
                    images = pdf_to_images(tmp_path, dpi=dpi)
                    if images:
                        pdf_idx = len(st.session_state.pdf_files)
                        st.session_state.pdf_files.append(uploaded_file)
                        st.session_state.pdf_names.append(uploaded_file.name)
                        st.session_state.all_images[pdf_idx] = images
                    
                    os.unlink(tmp_path)
        
        # Mostra PDFs carregados
        if st.session_state.pdf_files:
            total_pages = sum(len(images) for images in st.session_state.all_images.values())
            st.success(f"✅ {len(st.session_state.pdf_files)} PDF(s) carregado(s) | Total: {total_pages} páginas")
            
            # Lista de PDFs carregados
            with st.expander("📚 PDFs Carregados", expanded=False):
                for idx, pdf_name in enumerate(st.session_state.pdf_names):
                    pages_count = len(st.session_state.all_images[idx])
                    st.write(f"**{idx+1}. {pdf_name}**: {pages_count} páginas")
            
            # Interface de grupos
            st.markdown("### 📁 Grupos de Páginas")
            
            # Templates rápidos
            col1, col2 = st.columns([1, 3])
            with col1:
                template = st.selectbox(
                    "🎨 Aplicar Template",
                    options=['Personalizado'] + list(TEMPLATES.keys()),
                    help="Aplique um template predefinido ao grupo atual"
                )
                
                if template != 'Personalizado' and st.button("Aplicar"):
                    current_group = st.session_state.groups[st.session_state.current_group]
                    template_config = TEMPLATES[template]
                    for key, value in template_config.items():
                        current_group['config'][key] = value
                    st.rerun()
            
            # Gerenciamento de grupos
            col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 1])
            
            with col1:
                group_names = [g['name'] for g in st.session_state.groups]
                current_group_idx = st.selectbox(
                    "Grupo Atual",
                    range(len(st.session_state.groups)),
                    format_func=lambda x: st.session_state.groups[x]['name'],
                    index=st.session_state.current_group
                )
                st.session_state.current_group = current_group_idx
            
            with col2:
                if st.button("➕ Novo"):
                    new_group_num = len(st.session_state.groups) + 1
                    new_group = {
                        'name': f'Grupo {new_group_num}',
                        'pages': [],
                        'config': get_default_config()
                    }
                    st.session_state.groups.append(new_group)
                    st.session_state.current_group = len(st.session_state.groups) - 1
                    st.rerun()
            
            with col3:
                if st.button("📋 Duplicar"):
                    current = st.session_state.groups[st.session_state.current_group]
                    new_group = {
                        'name': f"{current['name']} (cópia)",
                        'pages': current['pages'].copy(),
                        'config': current['config'].copy()
                    }
                    st.session_state.groups.append(new_group)
                    st.session_state.current_group = len(st.session_state.groups) - 1
                    st.rerun()
            
            with col4:
                if st.button("📄 + Branco"):
                    current_group = st.session_state.groups[st.session_state.current_group]
                    current_group['pages'].append((-1, -1))  # -1 indica página em branco
                    st.rerun()
            
            with col5:
                if len(st.session_state.groups) > 1:
                    if st.button("🗑️ Remover"):
                        del st.session_state.groups[st.session_state.current_group]
                        st.session_state.current_group = min(st.session_state.current_group, len(st.session_state.groups) - 1)
                        st.rerun()
            
            # Renomear grupo
            current_group = st.session_state.groups[st.session_state.current_group]
            new_name = st.text_input("Nome do Grupo", value=current_group['name'], key=f"group_name_{st.session_state.current_group}")
            if new_name != current_group['name']:
                current_group['name'] = new_name
            
            # Mostra informações sobre todos os grupos
            with st.expander("📊 Resumo dos Grupos", expanded=False):
                for i, group in enumerate(st.session_state.groups):
                    pages_count = len(group['pages'])
                    if pages_count > 0:
                        pages_str = f"{pages_count} páginas"
                        grid_str = f"{group['config']['grid_cols']}x{group['config']['grid_rows']}"
                        orientation = group['config']['page_orientation']
                        st.write(f"**{group['name']}**: {pages_str} | Grid {grid_str} | {orientation}")
                    else:
                        st.write(f"**{group['name']}**: Nenhuma página selecionada")
            
            # Layout em duas colunas principais
            col_main, col_preview = st.columns([2, 1])
            
            with col_main:
                # Configurações do grupo atual
                with st.expander("⚙️ Configurações do Grupo", expanded=False):
                    config = current_group['config']
                    
                    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📐 Layout", "📏 Margens", "🎨 Aparência", "🖼️ Imagens", "💧 Extras"])
                    
                    with tab1:
                        col1, col2 = st.columns(2)
                        with col1:
                            config['page_size'] = st.selectbox(
                                "Tamanho do Papel",
                                options=list(PAGE_SIZES.keys()),
                                index=list(PAGE_SIZES.keys()).index(config['page_size']),
                                key=f"page_size_{st.session_state.current_group}"
                            )
                            
                            config['page_orientation'] = st.radio(
                                "Orientação da Página",
                                options=['Paisagem', 'Retrato'],
                                index=0 if config['page_orientation'] == 'Paisagem' else 1,
                                key=f"orientation_{st.session_state.current_group}"
                            )
                        
                        with col2:
                            config['grid_cols'] = st.number_input(
                                "Colunas no Grid",
                                min_value=1,
                                max_value=6,
                                value=config['grid_cols'],
                                key=f"grid_cols_{st.session_state.current_group}"
                            )
                            
                            config['grid_rows'] = st.number_input(
                                "Linhas no Grid",
                                min_value=1,
                                max_value=6,
                                value=config['grid_rows'],
                                key=f"grid_rows_{st.session_state.current_group}"
                            )
                        
                        total_slides = config['grid_cols'] * config['grid_rows']
                        st.info(f"💡 Total de {total_slides} slides por página neste grupo")
                    
                    with tab2:
                        col1, col2 = st.columns(2)
                        with col1:
                            config['margin_left'] = st.number_input(
                                "Margem Esquerda (cm)",
                                min_value=0.0,
                                max_value=10.0,
                                value=config['margin_left'],
                                step=0.5,
                                help="Recomendado: 3cm para fichário",
                                key=f"margin_left_{st.session_state.current_group}"
                            )
                            
                            config['margin_right'] = st.number_input(
                                "Margem Direita (cm)",
                                min_value=0.0,
                                max_value=10.0,
                                value=config['margin_right'],
                                step=0.5,
                                key=f"margin_right_{st.session_state.current_group}"
                            )
                        
                        with col2:
                            config['margin_top'] = st.number_input(
                                "Margem Superior (cm)",
                                min_value=0.0,
                                max_value=10.0,
                                value=config['margin_top'],
                                step=0.5,
                                key=f"margin_top_{st.session_state.current_group}"
                            )
                            
                            config['margin_bottom'] = st.number_input(
                                "Margem Inferior (cm)",
                                min_value=0.0,
                                max_value=10.0,
                                value=config['margin_bottom'],
                                step=0.5,
                                key=f"margin_bottom_{st.session_state.current_group}"
                            )
                        
                        config['spacing'] = st.slider(
                            "Espaçamento entre Slides (pixels)",
                            min_value=0,
                            max_value=50,
                            value=config['spacing'],
                            key=f"spacing_{st.session_state.current_group}"
                        )
                    
                    with tab3:
                        col1, col2 = st.columns(2)
                        with col1:
                            config['show_borders'] = st.checkbox(
                                "Mostrar Bordas",
                                value=config['show_borders'],
                                key=f"show_borders_{st.session_state.current_group}"
                            )
                            
                            if config['show_borders']:
                                config['border_width'] = st.slider(
                                    "Espessura da Borda",
                                    min_value=0.1,
                                    max_value=3.0,
                                    value=config['border_width'],
                                    step=0.1,
                                    key=f"border_width_{st.session_state.current_group}"
                                )
                            
                            config['show_numbers'] = st.checkbox(
                                "Mostrar Numeração",
                                value=config['show_numbers'],
                                key=f"show_numbers_{st.session_state.current_group}"
                            )
                        
                        with col2:
                            if config['show_numbers']:
                                config['number_size'] = st.slider(
                                    "Tamanho da Numeração",
                                    min_value=6,
                                    max_value=20,
                                    value=config['number_size'],
                                    key=f"number_size_{st.session_state.current_group}"
                                )
                                
                                config['number_position'] = st.selectbox(
                                    "Posição da Numeração",
                                    options=['Superior Esquerdo', 'Superior Direito', 
                                           'Inferior Esquerdo', 'Inferior Direito', 'Centro'],
                                    index=2,
                                    key=f"number_position_{st.session_state.current_group}"
                                )
                    
                    with tab4:
                        col1, col2 = st.columns(2)
                        with col1:
                            config['image_quality'] = st.select_slider(
                                "Qualidade da Imagem",
                                options=['Baixa', 'Média', 'Alta'],
                                value=config['image_quality'],
                                key=f"image_quality_{st.session_state.current_group}"
                            )
                            
                            config['rotate_images'] = st.slider(
                                "Rotação das Imagens (graus)",
                                min_value=0,
                                max_value=270,
                                value=config['rotate_images'],
                                step=90,
                                key=f"rotate_images_{st.session_state.current_group}"
                            )
                        
                        with col2:
                            config['image_orientation'] = st.selectbox(
                                "Orientação das Imagens",
                                options=['Manter Original', 'Forçar Paisagem', 'Forçar Retrato'],
                                index=0,
                                key=f"image_orientation_{st.session_state.current_group}"
                            )
                            
                            config['fit_mode'] = st.radio(
                                "Modo de Ajuste",
                                options=['Ajustar (manter visível)', 'Preencher (pode cortar)'],
                                index=0,
                                key=f"fit_mode_{st.session_state.current_group}"
                            )
                    
                    with tab5:
                        st.markdown("**Marca d'água**")
                        config['watermark_text'] = st.text_input(
                            "Texto da Marca d'água",
                            value=config.get('watermark_text', ''),
                            key=f"watermark_{st.session_state.current_group}",
                            help="Deixe vazio para não adicionar"
                        )
                        
                        if config['watermark_text']:
                            col1, col2 = st.columns(2)
                            with col1:
                                config['watermark_size'] = st.slider(
                                    "Tamanho",
                                    min_value=20,
                                    max_value=100,
                                    value=config.get('watermark_size', 40),
                                    key=f"watermark_size_{st.session_state.current_group}"
                                )
                            with col2:
                                config['watermark_opacity'] = st.slider(
                                    "Opacidade",
                                    min_value=0.05,
                                    max_value=0.5,
                                    value=config.get('watermark_opacity', 0.1),
                                    key=f"watermark_opacity_{st.session_state.current_group}"
                                )
                        
                        st.markdown("**Cabeçalho e Rodapé**")
                        config['header_text'] = st.text_input(
                            "Cabeçalho",
                            value=config.get('header_text', ''),
                            key=f"header_{st.session_state.current_group}",
                            help="Use {page} para número da página, {date} para data, {group} para nome do grupo"
                        )
                        
                        config['footer_text'] = st.text_input(
                            "Rodapé",
                            value=config.get('footer_text', ''),
                            key=f"footer_{st.session_state.current_group}",
                            help="Use {page} para número da página, {date} para data, {group} para nome do grupo"
                        )
                        
                        if config['header_text'] or config['footer_text']:
                            config['header_footer_size'] = st.slider(
                                "Tamanho do texto",
                                min_value=8,
                                max_value=16,
                                value=config.get('header_footer_size', 10),
                                key=f"header_footer_size_{st.session_state.current_group}"
                            )
                
                # Modo de seleção
                st.markdown(f"### 📑 Selecione as páginas para o **{current_group['name']}**")
                
                # Opções de visualização
                col1, col2, col3 = st.columns([1, 1, 2])
                with col1:
                    view_mode = st.radio(
                        "Visualizar",
                        options=['Por PDF', 'Todas'],
                        key="view_mode"
                    )
                
                with col2:
                    if view_mode == 'Por PDF' and len(st.session_state.pdf_files) > 1:
                        selected_pdf_idx = st.selectbox(
                            "PDF",
                            range(len(st.session_state.pdf_files)),
                            format_func=lambda x: st.session_state.pdf_names[x],
                            key="selected_pdf"
                        )
                    else:
                        selected_pdf_idx = None
                
                with col3:
                    sort_mode = st.selectbox(
                        "Ordenar páginas por",
                        options=['PDF → Página', 'Intercalar PDFs'],
                        key="sort_mode",
                        help="PDF → Página: todos do PDF1, depois PDF2...\nIntercalar: página 1 de cada PDF, depois página 2..."
                    )
                
                # Páginas já atribuídas a outros grupos
                pages_in_other_groups = set()
                for i, group in enumerate(st.session_state.groups):
                    if i != st.session_state.current_group:
                        pages_in_other_groups.update(group['pages'])
                
                # Botões de seleção rápida
                col1, col2, col3, col4, col5, col6 = st.columns(6)
                with col1:
                    if st.button("✅ Todas", key="select_all"):
                        if view_mode == 'Por PDF' and selected_pdf_idx is not None:
                            pdf_pages = [(selected_pdf_idx, i) for i in range(len(st.session_state.all_images[selected_pdf_idx]))]
                            current_group['pages'] = [p for p in pdf_pages if p not in pages_in_other_groups]
                        else:
                            all_pages = []
                            for pdf_idx, images in st.session_state.all_images.items():
                                all_pages.extend([(pdf_idx, i) for i in range(len(images))])
                            current_group['pages'] = [p for p in all_pages if p not in pages_in_other_groups]
                
                with col2:
                    if st.button("❌ Nenhuma", key="select_none"):
                        current_group['pages'] = [p for p in current_group['pages'] if p[0] == -1]  # Mantém apenas páginas em branco
                
                with col3:
                    if st.button("🔄 Inverter", key="invert"):
                        if view_mode == 'Por PDF' and selected_pdf_idx is not None:
                            pdf_pages = [(selected_pdf_idx, i) for i in range(len(st.session_state.all_images[selected_pdf_idx]))]
                            current_selected = set(p for p in current_group['pages'] if p[0] == selected_pdf_idx)
                            inverted = [p for p in pdf_pages if p not in current_selected and p not in pages_in_other_groups]
                            other_pdfs = [p for p in current_group['pages'] if p[0] != selected_pdf_idx]
                            current_group['pages'] = other_pdfs + inverted
                        else:
                            all_pages = []
                            for pdf_idx, images in st.session_state.all_images.items():
                                all_pages.extend([(pdf_idx, i) for i in range(len(images))])
                            current_selected = set(p for p in current_group['pages'] if p[0] != -1)
                            inverted = [p for p in all_pages if p not in current_selected and p not in pages_in_other_groups]
                            blank_pages = [p for p in current_group['pages'] if p[0] == -1]
                            current_group['pages'] = blank_pages + inverted
                
                with col4:
                    if st.button("📊 Pares", key="even"):
                        if view_mode == 'Por PDF' and selected_pdf_idx is not None:
                            pdf_pages = [(selected_pdf_idx, i) for i in range(len(st.session_state.all_images[selected_pdf_idx])) if i % 2 == 1]
                            current_group['pages'] = [p for p in pdf_pages if p not in pages_in_other_groups]
                        else:
                            all_pages = []
                            for pdf_idx, images in st.session_state.all_images.items():
                                all_pages.extend([(pdf_idx, i) for i in range(len(images)) if i % 2 == 1])
                            current_group['pages'] = [p for p in all_pages if p not in pages_in_other_groups]
                
                with col5:
                    if st.button("🚫 Sem grupo", key="unassigned"):
                        all_assigned = set()
                        for group in st.session_state.groups:
                            all_assigned.update(p for p in group['pages'] if p[0] != -1)
                        
                        unassigned = []
                        for pdf_idx, images in st.session_state.all_images.items():
                            unassigned.extend([(pdf_idx, i) for i in range(len(images)) 
                                             if (pdf_idx, i) not in all_assigned])
                        current_group['pages'] = unassigned
                
                with col6:
                    st.session_state.blank_pages_lined = st.checkbox("📝 Pautadas", value=False, help="Páginas em branco com linhas")
                
                # Grade de visualização
                cols_per_row = 4
                
                # Determina quais imagens mostrar
                if view_mode == 'Por PDF' and selected_pdf_idx is not None:
                    images_to_show = [(selected_pdf_idx, i, st.session_state.all_images[selected_pdf_idx][i]) 
                                     for i in range(len(st.session_state.all_images[selected_pdf_idx]))]
                else:
                    images_to_show = []
                    if sort_mode == 'PDF → Página':
                        for pdf_idx, images in st.session_state.all_images.items():
                            images_to_show.extend([(pdf_idx, i, images[i]) for i in range(len(images))])
                    else:  # Intercalar
                        max_pages = max(len(images) for images in st.session_state.all_images.values())
                        for page_num in range(max_pages):
                            for pdf_idx, images in st.session_state.all_images.items():
                                if page_num < len(images):
                                    images_to_show.append((pdf_idx, page_num, images[page_num]))
                
                # Adiciona páginas em branco do grupo
                blank_pages_in_group = [(idx, p) for idx, p in enumerate(current_group['pages']) if p[0] == -1]
                
                rows = (len(images_to_show) + cols_per_row - 1) // cols_per_row
                
                selected_pages = []
                
                for row in range(rows):
                    cols = st.columns(cols_per_row)
                    for col_idx in range(cols_per_row):
                        idx = row * cols_per_row + col_idx
                        if idx < len(images_to_show):
                            pdf_idx, page_idx, img = images_to_show[idx]
                            
                            with cols[col_idx]:
                                # Redimensiona a imagem
                                img_resized = img.copy()
                                img_resized.thumbnail((300, 300), Image.Resampling.LANCZOS)
                                
                                # Mostra a imagem
                                st.image(img_resized, use_container_width=True)
                                
                                # Verifica se está em outro grupo
                                page_tuple = (pdf_idx, page_idx)
                                in_other_group = page_tuple in pages_in_other_groups
                                other_group_name = ""
                                if in_other_group:
                                    for i, g in enumerate(st.session_state.groups):
                                        if i != st.session_state.current_group and page_tuple in g['pages']:
                                            other_group_name = g['name']
                                            break
                                
                                # Label
                                if len(st.session_state.pdf_files) > 1:
                                    pdf_name = st.session_state.pdf_names[pdf_idx]
                                    label = f"{pdf_name[:15]}... p{page_idx + 1}"
                                else:
                                    label = f"Página {page_idx + 1}"
                                
                                if in_other_group:
                                    label += f" ({other_group_name})"
                                
                                # Checkbox
                                is_selected = st.checkbox(
                                    label,
                                    value=page_tuple in current_group['pages'],
                                    key=f"page_{pdf_idx}_{page_idx}_group_{st.session_state.current_group}",
                                    disabled=in_other_group
                                )
                                
                                if is_selected and not in_other_group:
                                    selected_pages.append(page_tuple)
                
                # Atualiza as páginas selecionadas (mantém páginas em branco)
                blank_pages = [p for p in current_group['pages'] if p[0] == -1]
                current_group['pages'] = blank_pages + selected_pages
                
                # Mostra páginas em branco
                if blank_pages:
                    st.info(f"📄 {len(blank_pages)} página(s) em branco no grupo")
                
                # Contador
                real_pages = [p for p in current_group['pages'] if p[0] != -1]
                st.info(f"📊 {len(real_pages)} páginas selecionadas + {len(blank_pages)} em branco = {len(current_group['pages'])} total para {current_group['name']}")
            
            with col_preview:
                st.markdown("### 👁️ Preview do Layout")
                
                # Cabeçalho com nome do grupo e botão de atualizar
                col_title, col_refresh = st.columns([3, 1])
                with col_title:
                    st.markdown(f"**{current_group['name']}**")
                with col_refresh:
                    if st.button("🔄", help="Atualizar preview"):
                        st.rerun()
                
                # Cria o preview com as configurações atuais
                try:
                    # Para o preview, mostra sempre como página ímpar (não rotacionada)
                    preview_img = create_layout_preview(current_group['config'], len(current_group['pages']), page_number=1)
                    
                    # Cria uma string única baseada nas configurações principais
                    config_str = f"{current_group['config']['grid_cols']}x{current_group['config']['grid_rows']}"
                    config_str += f"_{current_group['config']['page_size']}_{current_group['config']['page_orientation']}"
                    config_str += f"_{current_group['config']['margin_left']}_{current_group['config']['margin_right']}"
                    config_str += f"_{current_group['config']['margin_top']}_{current_group['config']['margin_bottom']}"
                    config_str += f"_{current_group['config']['spacing']}_{current_group['config']['show_borders']}"
                    
                    # Mostra o preview
                    st.image(preview_img, use_container_width=True)
                    
                    # Se o modo fichário paisagem estiver ativo, mostra aviso
                    if st.session_state.get('landscape_binder_mode', False):
                        st.caption("🔄 Modo Fichário Paisagem: páginas pares (verso) serão rotacionadas 180°")
                except Exception as e:
                    st.error(f"Erro ao criar preview: {str(e)}")
                    st.info("Tente ajustar as configurações ou clique em 🔄 para atualizar")
                
                # Estatísticas do grupo
                config = current_group['config']
                total_slides_per_page = config['grid_cols'] * config['grid_rows']
                
                if current_group['pages']:
                    total_pages_in_group = (len(current_group['pages']) + total_slides_per_page - 1) // total_slides_per_page
                    economia = ((len(current_group['pages']) - total_pages_in_group) / len(current_group['pages']) * 100) if len(current_group['pages']) > 0 else 0
                    
                    st.markdown("#### 📊 Estatísticas do Grupo")
                    st.write(f"- Slides: {len(current_group['pages'])}")
                    st.write(f"- Páginas: {total_pages_in_group}")
                    st.write(f"- Por página: {total_slides_per_page}")
                    st.write(f"- Economia: {economia:.1f}%")
                
                # Estatísticas totais
                st.markdown("#### 📈 Total Geral")
                total_selected = sum(len(g['pages']) for g in st.session_state.groups)
                total_pages_final = sum(
                    (len(g['pages']) + g['config']['grid_cols'] * g['config']['grid_rows'] - 1) // 
                    (g['config']['grid_cols'] * g['config']['grid_rows'])
                    for g in st.session_state.groups if g['pages']
                )
                if total_selected > 0:
                    total_economia = ((total_selected - total_pages_final) / total_selected * 100)
                    st.write(f"- Total slides: {total_selected}")
                    st.write(f"- Total páginas: {total_pages_final}")
                    st.write(f"- Economia total: {total_economia:.1f}%")
                    
                    # Indicador do modo fichário
                    if st.session_state.get('landscape_binder_mode', False):
                        st.info("🔄 Modo Fichário Paisagem ativo: páginas pares serão rotacionadas 180°")
            
            # Configurações globais
            with st.expander("🌐 Configurações Globais", expanded=False):
                col1, col2 = st.columns(2)
                with col1:
                    st.session_state.global_watermark = st.text_input(
                        "Marca d'água global",
                        value=st.session_state.get('global_watermark', ''),
                        help="Aplica a todos os grupos que não têm marca d'água própria"
                    )
                    st.session_state.global_page_numbers = st.checkbox(
                        "Numeração global de páginas",
                        value=st.session_state.get('global_page_numbers', False),
                        help="Adiciona número de página no canto inferior direito"
                    )
                    st.session_state.pdf_dpi = st.selectbox(
                        "Qualidade de conversão (DPI)",
                        options=[100, 150, 200, 300],
                        index=1,
                        help="DPI maior = melhor qualidade mas processamento mais lento"
                    )
                with col2:
                    st.session_state.landscape_binder_mode = st.checkbox(
                        "🔄 Modo Fichário Paisagem",
                        value=st.session_state.get('landscape_binder_mode', False),
                        help="Rotaciona páginas pares (verso) em 180° para leitura em fichário paisagem sem precisar girar"
                    )
                    if st.session_state.landscape_binder_mode:
                        st.info("📋 Páginas pares serão rotacionadas 180° para facilitar leitura ao virar a página em fichários paisagem")
                        st.caption("💡 Use quando o fichário estiver em paisagem na mesa e você virar as páginas 'para cima'")
                
                # Configuração avançada do Poppler
                with st.expander("🔧 Configuração do Poppler (Avançado)", expanded=False):
                    st.info("Use apenas se o Poppler não for detectado automaticamente")
                    poppler_path = st.text_input(
                        "Caminho do Poppler (pasta bin)",
                        value=st.session_state.get('poppler_path', ''),
                        placeholder="Ex: C:\\poppler\\Library\\bin ou /usr/local/bin",
                        help="Caminho da pasta bin onde estão os executáveis do Poppler"
                    )
                    if poppler_path:
                        st.session_state.poppler_path = poppler_path
                        if st.button("Testar caminho"):
                            if os.path.exists(poppler_path):
                                st.success("✅ Caminho existe!")
                                # Força nova verificação
                                st.session_state.poppler_ok = check_poppler()
                                st.rerun()
                            else:
                                st.error("❌ Caminho não encontrado")
            
            # Botão para gerar PDF
            total_selected_all_groups = sum(len(g['pages']) for g in st.session_state.groups)
            if st.button("🚀 Gerar PDF Otimizado", type="primary", disabled=total_selected_all_groups == 0):
                if total_selected_all_groups > 0:
                    with st.spinner("Gerando PDF otimizado com todos os grupos..."):
                        output_path = tempfile.mktemp(suffix='.pdf')
                        create_optimized_pdf_with_groups(st.session_state.groups, st.session_state.all_images, output_path)
                        
                        with open(output_path, 'rb') as f:
                            pdf_data = f.read()
                        
                        # Estatísticas
                        groups_with_pages = [g for g in st.session_state.groups if g['pages']]
                        
                        success_msg = "✅ PDF otimizado gerado com sucesso!\n\n"
                        for group in groups_with_pages:
                            slides_count = len(group['pages'])
                            grid = group['config']['grid_cols'] * group['config']['grid_rows']
                            pages_count = (slides_count + grid - 1) // grid
                            success_msg += f"**{group['name']}**: {slides_count} slides em {pages_count} páginas (grid {group['config']['grid_cols']}x{group['config']['grid_rows']})\n\n"
                        
                        # Adiciona nota sobre modo fichário se ativo
                        if st.session_state.get('landscape_binder_mode', False):
                            success_msg += "\n🔄 **Modo Fichário Paisagem ativo**: Páginas pares (verso) foram rotacionadas 180° para facilitar leitura em fichários."
                        
                        st.success(success_msg)
                        
                        # Download
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"slides_otimizados_{timestamp}.pdf"
                        
                        st.download_button(
                            label="📥 Baixar PDF Otimizado",
                            data=pdf_data,
                            file_name=filename,
                            mime="application/pdf"
                        )
                        
                        os.unlink(output_path)
                else:
                    st.warning("⚠️ Por favor, selecione pelo menos uma página em algum grupo.")
    
    # Instruções
    with st.expander("ℹ️ Como usar este aplicativo"):
        st.markdown("""
        ### 🚀 Novidades da versão Multi-PDF:
        
        #### 📚 **Múltiplos PDFs**
        - Carregue vários PDFs de uma vez
        - Combine páginas de diferentes arquivos
        - Organize por PDF ou intercale páginas
        
        #### 🎨 **Templates Predefinidos**
        - **Padrão (2x2)**: Ideal para apresentações
        - **Econômico (3x3)**: Máxima economia de papel
        - **Revisão Rápida (4x4)**: Ver muito conteúdo de uma vez
        - **Anotações (1x2)**: Espaço para escrever
        - **Handout (2x3)**: Material para distribuir
        
        #### 📄 **Páginas em Branco**
        - Botão "📄 + Branco" adiciona páginas vazias
        - Opção de páginas pautadas para anotações
        - Útil para separar seções ou anotações
        
        #### 💧 **Marca d'água e Extras**
        - Marca d'água por grupo ou global
        - Cabeçalho e rodapé personalizados
        - Numeração global de páginas
        - Variáveis: {page}, {date}, {group}
        
        #### 🔀 **Modos de Ordenação**
        - **PDF → Página**: Agrupa por arquivo
        - **Intercalar PDFs**: Mistura páginas dos PDFs
        
        ### 💡 Exemplos de uso avançado:
        
        **Compilar material de múltiplas apresentações:**
        1. Carregue todos os PDFs
        2. Crie grupos temáticos
        3. Selecione páginas relevantes de cada PDF
        4. Adicione páginas em branco entre seções
        
        **Criar apostila com exercícios:**
        1. PDF 1: Teoria (2x2)
        2. PDF 2: Exercícios (1x1) 
        3. Páginas em branco pautadas para respostas
        4. Marca d'água com seu nome
        
        **Material para reunião:**
        1. Slides da apresentação (2x2)
        2. Gráficos detalhados (1x1)
        3. Anexos (3x3)
        4. Cabeçalho com data e projeto
        """)

# Exportar/Importar configurações
def export_config():
    config_data = {
        'groups': st.session_state.groups,
        'timestamp': datetime.now().isoformat()
    }
    return json.dumps(config_data, indent=2)

def import_config(config_json):
    try:
        config_data = json.loads(config_json)
        st.session_state.groups = config_data['groups']
        st.session_state.current_group = 0
        return True
    except:
        return False

if __name__ == "__main__":
    main()
