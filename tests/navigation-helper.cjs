// Exercise the actual disclosure rather than navigating through hidden links.
module.exports=async function clickNav(page,route){
 if(await page.locator('#header-menu-toggle').isVisible()&&await page.locator('#header-menu-toggle').getAttribute('aria-expanded')!=='true')await page.locator('#header-menu-toggle').click();
 if(['news','briefing','research'].includes(route)&&await page.locator('#news-menu-toggle').getAttribute('aria-expanded')!=='true')await page.locator('#news-menu-toggle').click();
 await page.locator(`.primary-navigation [data-nav="${route}"]`).click();
};
