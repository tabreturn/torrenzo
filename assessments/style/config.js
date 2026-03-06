module.exports = {
  stylesheet: ['style.css'],
  page_media_type: 'print',
  pdf_options: {
    displayHeaderFooter: true,
    headerTemplate: `
      <div style="width:100%; font-size:10px; text-align:center; color:#666; display:flex; align-items:center; justify-content:center; gap:8px;">
        <span>ver.2025-03-06</span>
      </div>
    `,
    footerTemplate: '<div style="width:100%; font-size:10px; text-align:center; color:#666;">Page <span class="pageNumber"></span> / <span class="totalPages"></span></div>'
  }
};
