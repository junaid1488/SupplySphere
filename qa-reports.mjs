export default async function run(page, ui) {
  // First click the Reports button
  await ui.click('@e10');
  // Wait for content to load
  await page.waitForTimeout(3000);
  // Snapshot again to get new refs
  return await ui.snapshot({full: true});
}