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
        // Activate all buttons with the same data-filter (sidebar + toolbar)
        const filter = btn.dataset.filter;
        document.querySelectorAll(`.filter-btn[data-filter="${filter}"]`)
            .forEach(b => b.classList.add('active'));

        document.querySelectorAll('.factura-card').forEach((card, i) => {
            const visible = filter === 'all' || card.dataset.estado === filter;
            card.style.display = visible ? '' : 'none';
            if (visible) {
                card.style.animationDelay = (i * 0.04) + 's';
                card.style.animation = 'none';
                card.offsetHeight;
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

    sec.innerHTML = '<span class="foto-uploading">Subiendo foto...</span>';

    const formData = new FormData();
    formData.append('foto', file);

    try {
        const res = await fetch(`/api/foto/${facturaId}`, {
            method: 'POST',
            body: formData,
        });

        if (res.ok) {
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

document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
        cerrarModal();
        const formModal = document.getElementById('form-modal');
        if (formModal && formModal.style.display !== 'none') cerrarFormPedido();
    }
});

// =========================================================
//  FORM PEDIDO MANUAL
// =========================================================
function abrirFormPedido() {
    const hoy = new Date().toLocaleDateString('en-CA');
    document.getElementById('form-fecha').value = hoy;
    document.getElementById('form-numero').value    = '';
    document.getElementById('form-cliente').value   = '';
    document.getElementById('form-domicilio').value = '';
    document.getElementById('form-items').innerHTML = '';
    ocultarErrorForm();
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
    const fechaISO  = document.getElementById('form-fecha').value;

    if (!cliente)   { mostrarErrorForm('El nombre del cliente es obligatorio.'); return; }
    if (!domicilio) { mostrarErrorForm('El domicilio es obligatorio.'); return; }

    let fecha = '';
    if (fechaISO) {
        const [y, m, d] = fechaISO.split('-');
        fecha = `${d}/${m}/${y}`;
    }

    const items = [];
    document.querySelectorAll('#form-items .form-item-row').forEach(row => {
        const cant = parseInt(row.querySelector('.item-cant').value) || 0;
        const det  = row.querySelector('.item-det').value.trim();
        if (det && cant > 0) {
            items.push({ cantidad: cant, detalle: det, precio_unit: 0, precio_total: 0 });
        }
    });

    const btn = document.getElementById('btn-guardar');
    btn.disabled    = true;
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
    const d = new Date(input.value + 'T12:00:00');
    d.setDate(d.getDate() + delta);
    const yyyy = d.getFullYear();
    const mm   = String(d.getMonth() + 1).padStart(2, '0');
    const dd   = String(d.getDate()).padStart(2, '0');
    irAFecha(`${yyyy}-${mm}-${dd}`);
}

// =========================================================
//  ELIMINAR FACTURA
// =========================================================
async function eliminarFactura(facturaId, numero) {
    if (!confirm(`¿Eliminar el pedido ${numero}?\nEsta acción no se puede deshacer.`)) return;

    try {
        const res = await fetch(`/api/factura/${facturaId}`, { method: 'DELETE' });
        if (res.ok) {
            const card = document.querySelector(`.factura-card[data-id="${facturaId}"]`);
            if (card) {
                card.style.transition = 'opacity .2s, transform .2s';
                card.style.opacity = '0';
                card.style.transform = 'scale(.95)';
                setTimeout(() => { card.remove(); }, 220);
            }
        } else {
            alert('Error al eliminar el pedido.');
        }
    } catch {
        alert('Error de conexión.');
    }
}

// =========================================================
//  LIMPIAR SIN ITEMS
// =========================================================
async function limpiarSinItems() {
    if (!confirm('¿Borrar todos los pedidos pendientes sin ítems?\n\nDespués ejecutá el watcher para reimportarlos con los datos completos.')) return;

    try {
        const res = await fetch('/api/facturas/limpiar-sin-items', { method: 'POST' });
        const data = await res.json().catch(() => ({}));
        if (res.ok) {
            alert(`Se eliminaron ${data.eliminadas} pedido(s) sin ítems.\n\nAhora ejecutá el watcher para reimportarlos.`);
            location.reload();
        } else {
            alert('Error: ' + (data.detail || 'No se pudo limpiar.'));
        }
    } catch {
        alert('Error de conexión.');
    }
}

// =========================================================
//  SIDEBAR TOGGLE (mobile)
// =========================================================
function toggleSidebar() {
    const sidebar  = document.getElementById('sidebar');
    const backdrop = document.getElementById('sidebar-backdrop');
    if (!sidebar) return;
    const isOpen = sidebar.classList.contains('is-open');
    sidebar.classList.toggle('is-open', !isOpen);
    backdrop && backdrop.classList.toggle('is-visible', !isOpen);
    document.body.style.overflow = isOpen ? '' : 'hidden';
}

// =========================================================
//  SCROLL — glassmorphism shadow on header
// =========================================================
(function initScrollHeader() {
    const header = document.getElementById('header');
    if (!header) return;
    const onScroll = () => header.classList.toggle('scrolled', window.scrollY > 10);
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
})();

// =========================================================
//  COUNT-UP — anima los números de estadísticas
// =========================================================
(function initCountUp() {
    const els = document.querySelectorAll('.stat-number[data-count]');
    if (!els.length) return;

    els.forEach(el => {
        const target = parseInt(el.dataset.count, 10) || 0;
        if (target === 0) return;
        el.textContent = '0';
        let start = null;
        const duration = 700;
        function step(ts) {
            if (!start) start = ts;
            const progress = Math.min((ts - start) / duration, 1);
            // ease-out cubic
            const eased = 1 - Math.pow(1 - progress, 3);
            el.textContent = Math.round(eased * target);
            if (progress < 1) requestAnimationFrame(step);
            else el.textContent = target;
        }
        requestAnimationFrame(step);
    });
})();

// =========================================================
//  INTERSECTION OBSERVER — fade-up cards on scroll
// =========================================================
(function initObserver() {
    const items = document.querySelectorAll('.observe-anim');
    if (!items.length) return;

    const io = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('in-view');
                io.unobserve(entry.target);
            }
        });
    }, { threshold: 0.08 });

    items.forEach((el, i) => {
        // stagger delay via inline style (add to existing animation-delay)
        const existing = parseFloat(el.style.animationDelay) || 0;
        el.style.transitionDelay = existing + 's';
        io.observe(el);
    });
})();

// =========================================================
//  RIPPLE — efecto ripple en botones con .ripple-host
// =========================================================
document.addEventListener('click', function(e) {
    const btn = e.target.closest('.ripple-host');
    if (!btn) return;

    const circle = document.createElement('span');
    circle.className = 'ripple-circle';
    const rect = btn.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height);
    circle.style.cssText = `
        width:${size}px; height:${size}px;
        left:${e.clientX - rect.left - size / 2}px;
        top:${e.clientY - rect.top  - size / 2}px;
    `;
    btn.appendChild(circle);
    circle.addEventListener('animationend', () => circle.remove());
});

// =========================================================
//  RIPPLE — agregar .ripple-host a todos los botones .btn
//  y pills (excepto disabled) en tiempo de ejecución
// =========================================================
(function addRippleToButtons() {
    document.querySelectorAll('.btn, .estado-pill, .filter-btn, .btn-big').forEach(btn => {
        if (!btn.disabled) btn.classList.add('ripple-host');
    });
})();

// =========================================================
//  FECHA LLEGADA — programar arribo automático
// =========================================================
function editarLlegada(facturaId, fechaActual) {
    const wrap = document.getElementById('llegada-input-' + facturaId);
    if (!wrap) return;
    const input = document.getElementById('llegada-date-' + facturaId);
    if (input && fechaActual) input.value = fechaActual;
    wrap.style.display = 'flex';
    if (input) input.focus();
}

function cancelarLlegada(facturaId) {
    const wrap = document.getElementById('llegada-input-' + facturaId);
    if (wrap) wrap.style.display = 'none';
}

async function guardarLlegada(facturaId) {
    const input = document.getElementById('llegada-date-' + facturaId);
    if (!input) return;
    const fecha = input.value.trim(); // YYYY-MM-DD o vacío

    const wrap = document.getElementById('llegada-input-' + facturaId);
    const sec  = document.getElementById('llegada-sec-' + facturaId);

    try {
        const res = await fetch(`/api/factura/${facturaId}/llegada`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ fecha }),
        });

        if (res.ok) {
            const data = await res.json();
            if (wrap) wrap.style.display = 'none';

            // Actualizar UI sin recargar
            if (sec) {
                if (data.display) {
                    sec.innerHTML = `
                        <div class="llegada-badge-row">
                            <span class="llegada-badge">📅 Llega el ${data.display}</span>
                            <button class="btn-edit-llegada" onclick="editarLlegada(${facturaId}, '${fecha}')" title="Cambiar fecha">✎</button>
                        </div>
                        <div class="llegada-input-wrap" id="llegada-input-${facturaId}" style="display:none">
                            <input type="date" id="llegada-date-${facturaId}" class="llegada-date-input" value="${fecha}">
                            <button class="btn-llegada-guardar ripple-host" onclick="guardarLlegada(${facturaId})">Guardar</button>
                            <button class="btn-llegada-cancel" onclick="cancelarLlegada(${facturaId})">✕</button>
                        </div>`;
                } else {
                    sec.innerHTML = `
                        <button class="btn-set-llegada" onclick="editarLlegada(${facturaId}, '')">
                            📅 Programar llegada
                        </button>
                        <div class="llegada-input-wrap" id="llegada-input-${facturaId}" style="display:none">
                            <input type="date" id="llegada-date-${facturaId}" class="llegada-date-input">
                            <button class="btn-llegada-guardar ripple-host" onclick="guardarLlegada(${facturaId})">Guardar</button>
                            <button class="btn-llegada-cancel" onclick="cancelarLlegada(${facturaId})">✕</button>
                        </div>`;
                }
            }
        } else {
            const err = await res.json().catch(() => ({}));
            alert('Error: ' + (err.detail || 'No se pudo guardar la fecha'));
        }
    } catch {
        alert('Error de conexión');
    }
}
