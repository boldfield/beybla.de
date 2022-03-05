$(document).ready(function(){
  $.getJSON("https://beybla.de/static/data/wa/metadata.json", function(data) {
    $.getJSON(data.epi.url, function(epi_data) {
      var latest_epi_deaths = epi_data[epi_data.length - 1].cumulative_deaths;
      var latest_epi_date = moment.unix(epi_data[epi_data.length - 1].date);
      $(".data-point.total-data-point").text(latest_epi_deaths.toLocaleString("en-US"));
      $(".total-as-of-date").text(
        latest_epi_date.format("YYYY-MM-DD")
      );
      var epi_last_thirty = 0;
      for (var i = 0; i < epi_data.length; i++) {
        var this_moment = moment.unix(epi_data[i].date);
        if (latest_epi_date.diff(this_moment, "days") <= 30) {
          epi_last_thirty = latest_epi_deaths - epi_data[i].cumulative_deaths
          break;
        }
      }
      $(".total-data-point-last-thirty").text(epi_last_thirty);
    })
    .done(function(epi_data) {
      $.getJSON(data.breakthrough.url, function(breakthrough_data) {
        var latest_epi_deaths = epi_data[epi_data.length - 1].cumulative_deaths;
        var latest_breakthrough_deaths = breakthrough_data[breakthrough_data.length - 1].cumulative_deaths;
        var latest_breakthrough_date = moment.unix(breakthrough_data[breakthrough_data.length - 1].end_date);
        $(".data-point.breakthrough-data-point").text(latest_breakthrough_deaths.toLocaleString("en-US"));
        $(".data-point.breakthrough-percentage").text(parseFloat(latest_breakthrough_deaths/latest_epi_deaths * 100).toFixed(2)+"%");
        $(".breakthrough-as-of-date").text(
          moment.unix(breakthrough_data[breakthrough_data.length - 1].end_date).format("YYYY-MM-DD")
        );
        var breakthrough_last_thirty = 0;
        for (var i = 0; i < breakthrough_data.length; i++) {
          var this_moment = moment.unix(breakthrough_data[i].end_date);
          if (latest_breakthrough_date.diff(this_moment, "days") <= 30) {
            breakthrough_last_thirty = latest_breakthrough_deaths - breakthrough_data[i].cumulative_deaths
            break;
          }
        }
        $(".breakthrough-data-point-last-thirty").text(breakthrough_last_thirty);

        var epi_plot_data = [];
        var breakthrough_plot_data = [];
        for (var i = 0; i < epi_data.length; i++) {
          epi_plot_data.push({
            x: moment.unix(epi_data[i].date).format("YYYY-MM-DD"),
            y: epi_data[i].cumulative_deaths,
          });
        };
        for (var i = 0; i < breakthrough_data.length; i++) {
          breakthrough_plot_data.push({
            x: moment.unix(breakthrough_data[i].end_date).format("YYYY-MM-DD"),
            y: breakthrough_data[i].cumulative_deaths,
          });
        };

        var epi_plot = {
          label: "Friends, family, and neighbors who died from covid, cumulative",
          borderColor: "black",
          data: epi_plot_data
        };

        var breakthrough_plot = {
          label: "Friends, family, and neighbors who died from breakthrough infections, cumulative",
          borderColor: "red",
          data: breakthrough_plot_data
        };

        var ctx = document.getElementById('cumulative-over-time').getContext('2d');
        //const ctx = $('#cumulative-over-time');
        var chart = new Chart(ctx, {
          type: 'line',
          data: { datasets: [epi_plot, breakthrough_plot] },
		  options: {
			scales: {
			  x: {
                type: 'time',
			  }
			},
            elements: {
              point: {
                radius: 5,
                borderWidth: 0
              }
            }
		  }
        });
      });
    });
  });
});
