// Actualiza el estado de una factura via API
async function setEstado(facturaId, estado, btn) {
    const original = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Actualizando...';

    try {
        const res = await fetch(`/api/estado/${facturaId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ estado }),
        });

        if (res.ok) {
            location.reload();
        } else {
            const err = await res.json().catch(() => ({}));
            alert('Error: ' + (err.detail || 'No se pudo actualizar el estado'));
            btn.disabled = false;
            btn.textContent = original;
        }
    } catch {
        alert('Error de conexión. Verificá que el servidor esté activo.');
        btn.disabled = false;
        btn.textContent = original;
    }
}

// Filtro de tarjetas por estado (solo en panel admin)
document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        const filter = btn.dataset.filter;
        document.querySelectorAll('.factura-card').forEach(card => {
            card.style.display =
                (filter === 'all' || card.dataset.estado === filter) ? '' : 'none';
        });
    });
});
