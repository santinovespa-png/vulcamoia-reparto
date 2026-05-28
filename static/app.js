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
//  FORM PEDIDO MANUAL
// =========================================================
function abrirFormPedido() {
    // Setear fecha de hoy por defecto
    const hoy = new Date().toLocaleDateString('en-CA'); // YYYY-MM-DD local
    document.getElementById('form-fecha').value = hoy;

    // Limpiar campos
    document.getElementById('form-numero').value    = '';
    document.getElementById('form-cliente').value   = '';
    document.getElementById('form-domicilio').value = '';
    document.getElementById('form-items').innerHTML = '';
    ocultarErrorForm();

    // Agregar una fila de item vacia para arrancar
    agregarItem();

    document.getElementById('form-modal').style.display = 'flex';
    document.body.style.overflow = 'hidden';
    setTimeout(() => document.getElementById('form-cliente').focus(), 100);
}

function cerrarFormPedido(e) {
    if (e && e.target !== document.getElementById('form-modal')) return;
    document.getElementById('form-modal').style.display = 'none';
    document.body.style.overflow = '';
}

function agregarItem() {
    const container = document.getElementById('form-items');
    const row = document.createElement('div');
    row.className = 'form-item-row';
    row.innerHTML = `
        <input type="number" class="item-cant" placeholder="Cant." min="1" value="1"
               style="width:72px">
        <input type="text" class="item-det" placeholder="Descripción del artículo">
        <button type="button" class="btn-remove" onclick="this.closest('.form-item-row').remove()"
                title="Quitar">✕</button>
    `;
    container.appendChild(row);
    row.querySelector('.item-det').focus();
}

function ocultarErrorForm() {
    const el = document.getElementById('form-error');
    el.style.display = 'none';
    el.textContent   = '';
}

function mostrarErrorForm(msg) {
    const el = document.getElementById('form-error');
    el.textContent   = msg;
    el.style.display = 'block';
}

async function guardarPedido() {
    ocultarErrorForm();

    const cliente   = document.getElementById('form-cliente').value.trim();
    const domicilio = document.getElementById('form-domicilio').value.trim();
    const numero    = document.getElementById('form-numero').value.trim();
    const fechaISO  = document.getElementById('form-fecha').value; // YYYY-MM-DD

    if (!cliente)   { mostrarErrorForm('El nombre del cliente es obligatorio.'); return; }
    if (!domicilio) { mostrarErrorForm('El domicilio es obligatorio.'); return; }

    // Convertir fecha YYYY-MM-DD → DD/MM/YYYY para la DB
    let fecha = '';
    if (fechaISO) {
        const [y, m, d] = fechaISO.split('-');
        fecha = `${d}/${m}/${y}`;
    }

    // Recolectar items
    const items = [];
    document.querySelectorAll('#form-items .form-item-row').forEach(row => {
        const cant = parseInt(row.querySelector('.item-cant').value) || 0;
        const det  = row.querySelector('.item-det').value.trim();
        if (det && cant > 0) {
            items.push({ cantidad: cant, detalle: det, precio_unit: 0, precio_total: 0 });
        }
    });

    const btn = document.getElementById('btn-guardar');
    btn.disabled   = true;
    btn.textContent = 'Guardando...';

    try {
        const res = await fetch('/api/factura', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({ numero, cliente, domicilio, fecha, items }),
        });

        const data = await res.json().catch(() => ({}));

        if (res.ok) {
            document.getElementById('form-modal').style.display = 'none';
            document.body.style.overflow = '';
            location.reload();
        } else {
            mostrarErrorForm(data.detail || 'Error al guardar el pedido.');
            btn.disabled    = false;
            btn.textContent = 'Guardar pedido';
        }
    } catch {
        mostrarErrorForm('Error de conexión. Verificá que el servidor esté activo.');
        btn.disabled    = false;
        btn.textContent = 'Guardar pedido';
    }
}

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
