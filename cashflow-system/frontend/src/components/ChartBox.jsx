import { useEffect, useRef, useState } from "react";

/**
 * Grafik uchun konteyner: kengligini o'zi o'lchaydi va bolasiga uzatadi.
 *
 * Nima uchun recharts'ning ResponsiveContainer'i ishlatilmaydi:
 *   U ba'zi holatlarda o'lchamni 0 deb hisoblab, grafikni umuman
 *   chizmay qo'yadi — konteyner DOM'da bo'lsa ham ichi bo'sh qoladi.
 *   Bu yerda kenglik ResizeObserver bilan aniq o'lchanadi, shuning uchun
 *   natija bashorat qilinadigan bo'ladi.
 *
 * Foydalanish:
 *   <ChartBox height={260}>
 *     {(width) => <ComposedChart width={width} height={260}>…</ComposedChart>}
 *   </ChartBox>
 */
export default function ChartBox({ height = 260, children }) {
  const ref = useRef(null);
  const [width, setWidth] = useState(0);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;

    const measure = () => setWidth(element.clientWidth);
    measure();

    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={ref} style={{ width: "100%", height, overflow: "hidden" }}>
      {width > 0 ? children(width) : null}
    </div>
  );
}
