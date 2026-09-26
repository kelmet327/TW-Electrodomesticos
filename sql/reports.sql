-- Consultas de apoyo para análisis y evaluación académica.
-- Ejecutar sobre la base bears_scourge después de cargar sql/schema.sql.

-- Ventas completadas por vendedor en un período.
SELECT u.nombre || ' ' || u.apellido AS vendedor,
       COUNT(v.id_venta) AS ventas,
       COALESCE(SUM(v.total), 0) AS ingresos
FROM usuario AS u
JOIN venta AS v ON v.id_vendedor = u.id_usuario
WHERE u.rol = 'vendedor'
  AND v.estado = 'completada'
  AND v.fecha_venta >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY u.id_usuario, u.nombre, u.apellido
ORDER BY ingresos DESC;

-- Ingresos por categoría.
SELECT c.nombre AS categoria,
       SUM(d.cantidad) AS unidades,
       SUM(d.subtotal) AS ingresos
FROM detalle_venta AS d
JOIN venta AS v ON v.id_venta = d.id_venta
JOIN producto AS p ON p.id_producto = d.id_producto
JOIN categoria AS c ON c.id_categoria = p.id_categoria
WHERE v.estado = 'completada'
GROUP BY c.id_categoria, c.nombre
ORDER BY ingresos DESC;

-- Productos con existencias bajas o agotadas.
SELECT p.id_producto, p.nombre, m.nombre AS marca, c.nombre AS categoria, p.stock
FROM producto AS p
JOIN marca AS m ON m.id_marca = p.id_marca
JOIN categoria AS c ON c.id_categoria = p.id_categoria
WHERE p.estado = TRUE AND p.stock <= 10
ORDER BY p.stock, p.nombre;

-- Historial de compras de un cliente.
SELECT v.id_venta, v.fecha_venta, v.total, v.estado, p.metodo, p.estado AS estado_pago
FROM venta AS v
JOIN pago AS p ON p.id_venta = v.id_venta
WHERE v.id_cliente = 1
ORDER BY v.fecha_venta DESC;
