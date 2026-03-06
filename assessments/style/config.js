module.exports = {
  stylesheet: ['style.css'],
  page_media_type: 'print',
  pdf_options: {
    format: 'A4',
    margin: '30mm 20mm 25mm 20mm',
    printBackground: true,
    displayHeaderFooter: true,
    headerTemplate: '<div style="width:100%; font-size:10px; text-align:center; color:#666;">ver.2025-03-06</div>',
    footerTemplate: '<div style="width:100%; font-size:10px; text-align:center; color:#666;">Page <span class="pageNumber"></span> / <span class="totalPages"></span></div>'
  }
};
