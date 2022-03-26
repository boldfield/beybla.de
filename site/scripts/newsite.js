$.BEYBLADE = {
  data: {},
  selectedState: null,
  metadata: {},
  supportedStates: ["CA", "WA"],
  chart: null,
  fetch_state_data: function(state) {
    $.BEYBLADE.selectedState = state;
    if (state in $.BEYBLADE.data) {
      $.BEYBLADE.refreshDisplay();
      return;
    }

    $.BEYBLADE.data[state] = {};
    $.BEYBLADE.metadata[state] = {};
    return $.getJSON("https://beybla.de/static/data/" + state + "/metadata.json", function(data) {
      $.BEYBLADE.metadata[state]["stateLabel"] = data["state_label"];
      $.BEYBLADE.metadata[state]["humanLabel"] = data["human_label"];
      $.BEYBLADE.metadata[state]["epi_url"] = data["epi"]["url"];
      $.BEYBLADE.metadata[state]["breakthrough_url"] = data["breakthrough"]["url"];

    })
    .then(function() {
      $.getJSON($.BEYBLADE.metadata[state]["epi_url"], function(epi_data) {
        $.BEYBLADE.data[state]["epi"] = epi_data;
      })
      .then(function() {
        $.getJSON($.BEYBLADE.metadata[state]["breakthrough_url"], function(breakthrough_data) {
          $.BEYBLADE.data[state]["breakthrough"] = breakthrough_data;
        })
        .then(function() {
          $.BEYBLADE.refreshDisplay();
        });
      });
    });
  },
  refreshDisplay: function() {
    var state = $.BEYBLADE.selectedState;
    location.hash = "#" + state;

    $(".state-label").text($.BEYBLADE.metadata[state]["stateLabel"]);
    $(".human-label").text($.BEYBLADE.metadata[state]["humanLabel"]);

    var epi_data = $.BEYBLADE.data[state]["epi"];
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

    var breakthrough_data = $.BEYBLADE.data[state]["breakthrough"];
    var latest_breakthrough_deaths = breakthrough_data[breakthrough_data.length - 1].cumulative_deaths;
    $(".data-point.breakthrough-data-point").text(latest_breakthrough_deaths.toLocaleString("en-US"));
    $(".data-point.breakthrough-percentage").text(parseFloat(latest_breakthrough_deaths/latest_epi_deaths * 100).toFixed(2)+"%");

    var latest_breakthrough_date = moment.unix(breakthrough_data[breakthrough_data.length - 1].date);
    $(".breakthrough-as-of-date").text(
      moment.unix(breakthrough_data[breakthrough_data.length - 1].date).format("YYYY-MM-DD")
    );
    var breakthrough_last_thirty = 0;
    for (var i = 0; i < breakthrough_data.length; i++) {
      var this_moment = moment.unix(breakthrough_data[i].date);
      if (latest_breakthrough_date.diff(this_moment, "days") <= 30) {
        breakthrough_last_thirty = latest_breakthrough_deaths - breakthrough_data[i].cumulative_deaths
        break;
      }
    }
    $(".breakthrough-data-point-last-thirty").text(breakthrough_last_thirty);
    $.BEYBLADE.plotData();
  },
  plotData: function() {
    var state = $.BEYBLADE.selectedState;
    var epi_plot_data = [];
    var breakthrough_plot_data = [];
    var last_breakthrough_ts = 0;

    var epi_data = $.BEYBLADE.data[state]["epi"];
    var breakthrough_data = $.BEYBLADE.data[state]["breakthrough"];

    for (var i = 0; i < breakthrough_data.length; i++) {
      breakthrough_plot_data.push({
        x: moment.unix(breakthrough_data[i].date).format("YYYY-MM-DD"),
        y: breakthrough_data[i].cumulative_deaths,
      });
      last_breakthrough_ts = breakthrough_data[i].date;
    };
    for (var i = 0; i < epi_data.length; i++) {
      if (epi_data[i].date > last_breakthrough_ts) {
        continue;
      }
      epi_plot_data.push({
        x: moment.unix(epi_data[i].date).format("YYYY-MM-DD"),
        y: epi_data[i].cumulative_deaths,
      });
    };

    var epi_plot = {
      label: $.BEYBLADE.metadata[state]["humanLabel"] + " who have died from covid, cumulative",
      borderColor: "black",
      data: epi_plot_data
    };

    var breakthrough_plot = {
      label: $.BEYBLADE.metadata[state]["humanLabel"] + " who have died from breakthrough infections, cumulative",
      borderColor: "red",
      data: breakthrough_plot_data
    };

    if ($.BEYBLADE.chart) {
      $.BEYBLADE.chart.destroy();
      $.BEYBLADE.chart = null;
    }
    var ctx = document.getElementById('cumulative-over-time').getContext('2d');
    //const ctx = $('#cumulative-over-time');
    $.BEYBLADE.chart = new Chart(ctx, {
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
  }
}

$(document).ready(function(){
  $('#map').usmap({
    showLabels: false,
    stateStyles: {fill: '#383838'},
    stateHoverStyles: {fill: '#383838'},
    stateSpecificStyles: {
      'WA': {fill: 'yellow'},
      'CA': {fill: 'yellow'}
    },
    stateSpecificHoverStyles: {
      'WA': {fill: 'red'},
      'CA': {fill: 'red'}
    },
    click: function(event, data) {
      var state = data.name.toLowerCase();
      $.BEYBLADE.fetch_state_data(state);
    }
  });

  if (location.hash != "" && $.BEYBLADE.supportedStates.includes(location.hash.substr(1).toUpperCase())) {
    var state = location.hash.substr(1).toLowerCase();
    $.BEYBLADE.fetch_state_data(state);
  } else {
    $.BEYBLADE.fetch_state_data("WA");
  }

});
