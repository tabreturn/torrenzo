module.exports = {
  stylesheet: ['style.css'],
  page_media_type: 'print',
  pdf_options: {
    displayHeaderFooter: true,
    margin: '25mm 20mm',
    headerTemplate: `
      <style>
        @font-face {
          font-family: InterVariable;
          src: url("style/InterVariable.ttf") format("truetype");
        }
        .hdr {
          width: 100%;
          font-size: 10px;
          color: #666;
          text-align: center;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          padding: 0 12px;
        }
        .hdr .ver { font-family: InterVariable, sans-serif; }
        .hdr svg { height: 2cm; width: auto }
      </style>
      <div class="hdr">
        <!--INLINE_LOGO_MARKUP-->
        <span class="ver">ver.2025-03-06</span>
      </div>
    `,
    footerTemplate: '<div style="width:100%; font-size:10px; text-align:center; color:#666;">Page <span class="pageNumber"></span> / <span class="totalPages"></span></div>'
  }
};
