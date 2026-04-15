$(document).ready( function () {
  new DataTable('#jobsTable', {
    paging: false,
    ordering: false,
    layout: {
      topStart: null,
      topEnd: null,
      bottomStart: null,
      bottomEnd: null
    },
    columnDefs: [
      {
        targets: [1, 2, 3, 4, 7],
        columnControl: [['searchList']]
      },
      {
        targets: [5, 6],
        columnControl: {
            target: 0,
            content: ['searchDateTime']
            }
        }
    ],
    responsive: true
  });
} );