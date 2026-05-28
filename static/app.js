// =========================================================
//  ESTADO — cambiar estado de factura
// =========================================================
async function setEstado(facturaId, estado, btn) {
    const original = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span style="opacity:.6">Actualizando...</span>';

    try {
        const res = await fetch(`/api/estado/${facturaId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ estado }),
        });

        if (res.ok) {
            // Animacion de salida antes de recargar
            const card = btn.closest('.factura-card, .delivery-card');
            if (card) {
                card.style.transition = 'opacity .25s, transform .25s';
                card.style.opacity = '0';
                card.style.transform = 'scale(.97)';
            }
            setTimeout(() => location.reload(), 260);
        } else {
            const err = await res.json().catch(() => ({}));
            alert('Error: ' + (err.detail || 'No se pudo actualizar'));
            btn.disabled = false;
            btn.innerHTML = original;
        }
    } catch {
        alert('Error de conexión. Verificá que el servidor esté activo.');
        btn.disabled = false;
        btn.innerHTML = original;
    }
}

// =========================================================
//  FILTRO — panel admin
// =========================================================
document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        const filter = btn.dataset.filter;
        document.querySelectorAll('.factura-card').forEach((card, i) => {
            const visible = filter === 'all' || card.dataset.estado === filter;
            card.style.display = visible ? '' : 'none';
            if (visible) {
                card.style.animationDelay = (i * 0.04) + 's';
                card.style.animation = 'none';
                card.offsetHeight; // reflow
                card.style.animation = '';
            }
        });
    });
});

// =========================================================
//  FOTO — subir foto del remito
// =========================================================
async function subirFoto(facturaId, input) {
    const file = input.files[0];
    if (!file) return;

    const sec = document.getElementById('foto-sec-' + facturaId);
    if (!sec) return;

    // Mostrar estado de carga
    sec.innerHTML = '<span class="foto-uploading">Subiendo foto...</span>';

    const formData = new FormData();
    formData.append('foto', file);

    try {
        const res = await fetch(`/api/foto/${facturaId}`, {
            method: 'POST',
            body: formData,
        });

        if (res.ok) {
            // Mostrar thumbnail
            const url = `/api/foto/${facturaId}?t=${Date.now()}`;
            sec.innerHTML = `
                <div class="foto-thumb-wrapper">
                    <img class="foto-thumb" src="${url}" alt="Remito"
                         onclick="verFoto(this.src)">
                    <span class="foto-ok">✓ Remito fotografiado</span>
                </div>`;
        } else {
            const err = await res.json().catch(() => ({}));
            alert('Error al subir: ' + (err.detail || 'intente de nuevo'));
            // Restaurar boton
            sec.innerHTML = `
                <label class="foto-upload-label">
                    📷 Subir foto del remito
                    <input type="file" accept="image/*" capture="environment"
                           onchange="subirFoto(${facturaId}, this)">
                </label>`;
        }
    } catch {
        alert('Error de conexión al subir la foto.');
        sec.innerHTML = `
            <label class="foto-upload-label">
                📷 Subir foto del remito
                <input type="file" accept="image/*"
                       onchange="subirFoto(${facturaId}, this)">
            </label>`;
    }
}

// =========================================================
//  MODAL — ver foto en pantalla completa
// =========================================================
function verFoto(src) {
    const modal = document.getElementById('foto-modal');
    const img   = document.getElementById('foto-modal-img');
    img.src = src;
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
}

function cerrarModal() {
    const modal = document.getElementById('foto-modal');
    modal.style.display = 'none';
    document.getElementById('foto-modal-img').src = '';
    document.body.style.overflow = '';
}

// Cerrar modal con ESC
document.addEventListener('keydown', e => {
    if (e.key === 'Escape') cerrarModal();
});

// =========================================================
//  NAVEGACION DE FECHA (panel admin)
// =========================================================
function irAFecha(fecha) {
    const url = new URL(window.location.href);
    url.searchParams.set('fecha', fecha);
    window.location.href = url.toString();
}

function navegarFecha(delta) {
    const input = document.getElementById('fecha-input');
    if (!input) return;
    const d = new Date(input.value + 'T12:00:00'); // noon para evitar timezone issues
    d.setDate(d.getDate() + delta);
    const yyyy = d.getFullYear();
    const mm   = String(d.getMonth() + 1).padStart(2, '0');
    const dd   = String(d.getDate()).padStart(2, '0');
    irAFecha(`${yyyy}-${mm}-${dd}`);
}
