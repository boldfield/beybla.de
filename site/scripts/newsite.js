$.BEYBLADE = {
  data: {},
  selectedState: null,
  metadata: {},
  supportedStates: [],
  chart: null,
  mixpanel: null,
  fetchSupportedStates: function() {
    this.supportedStates = ["CA", "WA"];
  },
  fetchStateData: function(state) {
    this.selectedState = state;
    if (state in this.data) {
      this.refreshDisplay();
      return;
    }

    this.data[state] = {};
    this.metadata[state] = {};
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
    var state = this.selectedState;
    location.hash = "#" + state;
    if (location.host == "baybla.de") {
      mixpanel.track('load-' + state);
    }

    $(".state-label").text(this.metadata[state]["stateLabel"]);
    $(".human-label").text(this.metadata[state]["humanLabel"]);

    var breakthrough_data = this.data[state]["breakthrough"];
    var latest_breakthrough_deaths = breakthrough_data[breakthrough_data.length - 1].cumulative_deaths;
    var latest_breakthrough_date = moment.unix(breakthrough_data[breakthrough_data.length - 1].date);

    $(".data-point.breakthrough-data-point").text(latest_breakthrough_deaths.toLocaleString("en-US"));

    $(".breakthrough-as-of-date").text(
      moment.unix(breakthrough_data[breakthrough_data.length - 1].date).format("YYYY-MM-DD")
    );


    var epi_data = this.data[state]["epi"];
    var latest_epi_date = moment.unix(epi_data[epi_data.length - 1].date);
    var latest_epi_deaths = epi_data[epi_data.length - 1].cumulative_deaths;
    $(".data-point.total-data-point").text(latest_epi_deaths.toLocaleString("en-US"));
    $(".total-as-of-date").text(
      latest_epi_date.format("YYYY-MM-DD")
    );

    $(".data-point.breakthrough-percentage").text(parseFloat(latest_breakthrough_deaths/latest_epi_deaths * 100).toFixed(2)+"%");

    this.plotData();
  },
  plotData: function() {
    var state = this.selectedState;
    var epi_plot_data = [];
    var breakthrough_plot_data = [];
    var last_breakthrough_ts = 0;

    var epi_data = this.data[state]["epi"];
    var breakthrough_data = this.data[state]["breakthrough"];

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
      label: this.metadata[state]["humanLabel"] + " who have died from covid, cumulative",
      borderColor: "black",
      data: epi_plot_data
    };

    var breakthrough_plot = {
      label: this.metadata[state]["humanLabel"] + " who have died from breakthrough infections, cumulative",
      borderColor: "red",
      data: breakthrough_plot_data
    };

    if (this.chart) {
      this.chart.destroy();
      this.chart = null;
    }
    var ctx = document.getElementById('cumulative-over-time').getContext('2d');
    this.chart = new Chart(ctx, {
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
  },
  setupMixpanel: function() {
    if (!!this.mixpanel || (location.host != "beybla.de")) {
      return;
    }
    (function(f,b){if(!b.__SV){var e,g,i,h;window.mixpanel=b;b._i=[];b.init=function(e,f,c){function g(a,d){var b=d.split(".");2==b.length&&(a=a[b[0]],d=b[1]);a[d]=function(){a.push([d].concat(Array.prototype.slice.call(arguments,0)))}}var a=b;"undefined"!==typeof c?a=b[c]=[]:c="mixpanel";a.people=a.people||[];a.toString=function(a){var d="mixpanel";"mixpanel"!==c&&(d+="."+c);a||(d+=" (stub)");return d};a.people.toString=function(){return a.toString(1)+".people (stub)"};i="disable time_event track track_pageview track_links track_forms track_with_groups add_group set_group remove_group register register_once alias unregister identify name_tag set_config reset opt_in_tracking opt_out_tracking has_opted_in_tracking has_opted_out_tracking clear_opt_in_out_tracking start_batch_senders people.set people.set_once people.unset people.increment people.append people.union people.track_charge people.clear_charges people.delete_user people.remove".split(" ");
    for(h=0;h<i.length;h++)g(a,i[h]);var j="set set_once union unset remove delete".split(" ");a.get_group=function(){function b(c){d[c]=function(){call2_args=arguments;call2=[c].concat(Array.prototype.slice.call(call2_args,0));a.push([e,call2])}}for(var d={},e=["get_group"].concat(Array.prototype.slice.call(arguments,0)),c=0;c<j.length;c++)b(j[c]);return d};b._i.push([e,f,c])};b.__SV=1.2;e=f.createElement("script");e.type="text/javascript";e.async=!0;e.src="undefined"!==typeof MIXPANEL_CUSTOM_LIB_URL?
    MIXPANEL_CUSTOM_LIB_URL:"file:"===f.location.protocol&&"//cdn.mxpnl.com/libs/mixpanel-2-latest.min.js".match(/^\/\//)?"https://cdn.mxpnl.com/libs/mixpanel-2-latest.min.js":"//cdn.mxpnl.com/libs/mixpanel-2-latest.min.js";g=f.getElementsByTagName("script")[0];g.parentNode.insertBefore(e,g)}})(document,window.mixpanel||[]);
    mixpanel.init('574994a080b8cdb4d4f5b82ef68f5c44');
    mixpanel.track('load-index');
    this.mixpanel = mixpanel;
  }
}

$(document).ready(function(){
  $.BEYBLADE.setupMixpanel();
  $.BEYBLADE.fetchSupportedStates();
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
      $.BEYBLADE.fetchStateData(state);
    }
  });

  if (location.hash != "" && $.BEYBLADE.supportedStates.includes(location.hash.substr(1).toUpperCase())) {
    var state = location.hash.substr(1).toLowerCase();
    $.BEYBLADE.fetchStateData(state);
  } else {
    $.BEYBLADE.fetchStateData("wa");
  }

});
