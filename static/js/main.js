document.addEventListener('DOMContentLoaded', function() {
    // Configuración inicial
    document.getElementById('currentYear').textContent = new Date().getFullYear();
    
    // Elementos del DOM
    const converterForm = document.getElementById('converterForm');
    const urlInput = document.getElementById('url');
    const formatSelect = document.getElementById('format');
    const convertBtn = document.getElementById('convertBtn');
    const btnText = document.getElementById('btnText');
    const btnSpinner = document.getElementById('btnSpinner');
    const progressContainer = document.getElementById('progressContainer');
    const progressBar = document.getElementById('progressBar');
    const statusDiv = document.getElementById('status');
    
    // Evento del formulario
    converterForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const url = urlInput.value.trim();
        const format = formatSelect.value;
        
        // Validaciones
        if (!url) {
            showStatus('Por favor ingresa una URL válida', 'danger');
            return;
        }

        if (!isValidYouTubeUrl(url)) {
            showStatus('URL de YouTube no válida', 'danger');
            return;
        }

        // Estado de carga
        convertBtn.disabled = true;
        btnText.innerHTML = '<i class="fas fa-cog fa-spin me-2"></i>Procesando...';
        btnSpinner.classList.remove('d-none');
        progressContainer.classList.remove('d-none');
        statusDiv.classList.add('d-none');
        updateProgress(10);

        try {
            const response = await fetch('/convert', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    url: url,
                    format: format
                })
            });

            updateProgress(30);
            
            if (!response.ok) {
                const errorData = await response.json();
                let errorMsg = errorData.error || 'Error en la conversión';
                
                if (response.status === 401 || response.status === 500) {
                    errorMsg = `
                        <strong>${errorMsg}</strong><br>
                        <small>${errorData.solutions?.join('<br>') || 'Intenta más tarde'}</small>
                    `;
                }
                
                throw new Error(errorMsg);
            }

            updateProgress(70);
            
            const blob = await response.blob();
            updateProgress(90);

            // Nombre del archivo
            let filename = `video.${format}`;
            const contentDisposition = response.headers.get('Content-Disposition');
            if (contentDisposition) {
                const match = contentDisposition.match(/filename="(.+)"/);
                if (match && match[1]) filename = match[1];
            }

            // Descarga
            const downloadUrl = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = downloadUrl;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(downloadUrl);
            a.remove();

            updateProgress(100);
            showStatus('¡Descarga completada!', 'success');
        } catch (error) {
            showStatus(`Error: ${error.message}`, 'danger');
            console.error('Error:', error);
        } finally {
            setTimeout(() => {
                convertBtn.disabled = false;
                btnText.innerHTML = '<i class="fas fa-download me-2"></i>Convertir y Descargar';
                btnSpinner.classList.add('d-none');
                progressContainer.classList.add('d-none');
                progressBar.style.width = '0%';
            }, 1000);
        }
    });

    // Funciones auxiliares
    function isValidYouTubeUrl(url) {
        return /^(https?:\/\/)?(www\.)?(youtube\.com|youtu\.be)\/.+/.test(url);
    }

    function showStatus(message, type) {
        statusDiv.innerHTML = message;
        statusDiv.className = `alert alert-${type} fade-in`;
        statusDiv.classList.remove('d-none');
    }

    function updateProgress(percent) {
        progressBar.style.width = percent + '%';
    }
});