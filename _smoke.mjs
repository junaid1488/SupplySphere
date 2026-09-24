export default async function run(page, ui) {
  await page.waitForTimeout(3000)

  const result = await page.evaluate(() => {
    const text = document.body.innerText
    const buttons = Array.from(document.querySelectorAll('button')).map((b) => b.textContent?.trim())
    const selects = Array.from(document.querySelectorAll('select')).map((s) => ({
      aria: s.getAttribute('aria-label'),
      value: s.value,
      options: Array.from(s.options).map((o) => o.textContent),
    }))
    const markers = document.querySelectorAll('.warehouse-marker').length
    const polylines = document.querySelectorAll('path').length
    return {
      hasControlTower: !!document.querySelector('.map-shell'),
      bodyChars: text.length,
      warehouseButton: buttons.find((b) => b && b.includes('Warehouses')) || null,
      shippingButton: buttons.find((b) => b && b.includes('Shipping')) || null,
      networkSelect: selects.find((s) => s.aria === 'Operational network') || null,
      markers,
      polylines,
      snippet: text.slice(0, 500),
    }
  })

  return { result }
}
