// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

const LogUtil = (function() {
  /**
   * Gather any tab-specific state information prior to creating a log dump.
   */
  function getTabData_() {
    const tabData = {};
    const tabSwitcher = MainView.getInstance().tabSwitcher();
    const tabIdToView = tabSwitcher.getAllTabViews();
    for (const tabId in tabIdToView) {
      const view = tabIdToView[tabId];
      if (view.saveState) {
        tabData[tabId] = view.saveState();
      }
    }
  }

  /**
   * Loads a full log dump.  Returns a string containing a log of the load.
   * |opt_fileName| should always be given when loading from a file, instead of
   * from a log dump generated in-memory.
   * The process goes like this:
   * 1)  Load constants.  If this fails, or the version number can't be handled,
   *     abort the load.  If this step succeeds, the load cannot be aborted.
   * 2)  Clear all events.  Any event observers are informed of the clear as
   *     normal.
   * 3)  Call onLoadLogStart(polledData, tabData) for each view with an
   *     onLoadLogStart function.  This allows tabs to clear any extra state
   *     that would affect the next step.  |polledData| contains the data polled
   *     for all helpers, but |tabData| contains only the data from that
   *     specific tab.
   * 4)  Add all events from the log file.
   * 5)  Call onLoadLogFinish(polledData, tabData) for each view with an
   *     onLoadLogFinish function.  The arguments are the same as in step 3.  If
   *     there is no onLoadLogFinish function, it throws an exception, or it
   *     returns false instead of true, the data dump is assumed to contain no
   *     valid data for the tab, so the tab is hidden.  Otherwise, the tab is
   *     shown.
   */
  function loadLogDump(logDump, opt_fileName) {
    // Perform minimal validity check, and abort if it fails.
    if (typeof(logDump) !== 'object') {
      return 'Load failed.  Top level JSON data is not an object.';
    }

    // String listing text summary of load errors, if any.
    let errorString = '';

    if (!areValidConstants(logDump.constants)) {
      errorString += 'Invalid constants object.\n';
    }
    if (typeof(logDump.events) !== 'object') {
      errorString += 'NetLog events missing.\n';
    }
    if (logDump.constants &&
        typeof(logDump.constants.logFormatVersion) !== 'number') {
      errorString += 'Invalid version number.\n';
    }

    if (errorString.length > 0) {
      return 'Load failed:\n\n' + errorString;
    }

    if (typeof(logDump.polledData) !== 'object') {
      logDump.polledData = {};
    }
    if (typeof(logDump.tabData) !== 'object') {
      logDump.tabData = {};
    }

    const kSupportedLogFormatVersion = 1;

    if (logDump.constants.logFormatVersion !== kSupportedLogFormatVersion) {
      return 'Unable to load different log version.' +
          ' Found ' + logDump.constants.logFormatVersion + ', Expected ' +
          Constants.logFormatVersion;
    }

    g_browser.receivedConstants(logDump.constants);

    // Check for validity of each log entry, and then add the ones that pass.
    // Since the events are kept around, and we can't just hide a single view
    // on a bad event, we have more error checking for them than other data.
    const validEvents = [];
    let numDeprecatedPassiveEvents = 0;
    for (let eventIndex = 0; eventIndex < logDump.events.length; ++eventIndex) {
      const event = logDump.events[eventIndex];
      if (typeof event === 'object' && typeof event.source === 'object' &&
          typeof event.time === 'string' &&
          typeof EventTypeNames[event.type] === 'string' &&
          typeof EventSourceTypeNames[event.source.type] === 'string' &&
          getKeyWithValue(EventPhase, event.phase) !== '?') {
        if (event.wasPassivelyCaptured) {
          // NOTE: Up until Chrome 18, log dumps included "passively captured"
          // events. These are no longer supported, so skip past them
          // to avoid confusing the rest of the code.
          numDeprecatedPassiveEvents++;
          continue;
        }
        validEvents.push(event);
      }
    }

    // Determine the export date for the loaded log.
    //
    // Dumps created from chrome://net-internals (Chrome 17 - Chrome 59) will
    // have this set in constants.clientInfo.numericDate.
    //
    // However more recent dumping mechanisms (chrome://net-export/ and
    // --log-net-log) write the constants object directly to a file when the
    // dump is *started* so lack this ability.
    //
    // In this case, we will synthesize this field by looking at the timestamp
    // of the last event logged. In practice this works fine since there tend
    // to be lots of events logged.
    //
    // TODO(eroman): Fix the log format / writers to avoid this problem. Dumps
    // *should* contain the time when capturing started, and when capturing
    // ended.
    if (typeof logDump.constants.clientInfo.numericDate !== 'number') {
      if (validEvents.length > 0) {
        const lastEvent = validEvents[validEvents.length - 1];
        ClientInfo.numericDate =
            timeutil.convertTimeTicksToDate(lastEvent.time).getTime();
      } else {
        errorString += 'Can\'t guess export date as there are no events.\n';
        ClientInfo.numericDate = 0;
      }
    }

    // Prevent communication with the browser.  Once the constants have been
    // loaded, it's safer to continue trying to load the log, even in the case
    // of bad data.
    MainView.getInstance().onLoadLog(opt_fileName);

    // Delete all events.  This will also update all logObservers.
    EventsTracker.getInstance().deleteAllLogEntries();

    // Inform all the views that a log file is being loaded, and pass in
    // view-specific saved state, if any.
    const tabSwitcher = MainView.getInstance().tabSwitcher();
    const tabIdToView = tabSwitcher.getAllTabViews();
    for (const tabId in tabIdToView) {
      const view = tabIdToView[tabId];
      view.onLoadLogStart(logDump.polledData, logDump.tabData[tabId]);
    }
    EventsTracker.getInstance().addLogEntries(validEvents);

    const numInvalidEvents = logDump.events.length -
        (validEvents.length + numDeprecatedPassiveEvents);
    if (numInvalidEvents > 0) {
      errorString += 'Unable to load ' + numInvalidEvents +
          ' events, due to invalid data.\n\n';
    }

    if (numDeprecatedPassiveEvents > 0) {
      errorString += 'Discarded ' + numDeprecatedPassiveEvents +
          ' passively collected events. Use an older version of Chrome to' +
          ' load this dump if you want to see them.\n\n';
    }

    // Update all views with data from the file.  Show only those views which
    // successfully load the data.
    for (const tabId in tabIdToView) {
      const view = tabIdToView[tabId];
      let showView = false;
      // The try block eliminates the need for checking every single value
      // before trying to access it.
      try {
        if (view.onLoadLogFinish(
            logDump.polledData, logDump.tabData[tabId], logDump)) {
          showView = true;
        }
      } catch (error) {
        errorString +=
            'Caught error while calling onLoadLogFinish: ' + error + '\n\n';
      }
      tabSwitcher.showTabLink(tabId, showView);
    }

    return errorString + 'Log loaded.';
  }

  /**
   * Attempts to parse |logFileContents| as an NDJSON NetLog dump, as written
   * by --net-log-file-format=ndjson.  Such logs contain one JSON record per
   * line, each identified by a "type" field:
   *
   *   {"type":"constants","constants":{...}}   (always the first line)
   *   {"type":"event","event":{...}}
   *   {"type":"polledData","polledData":{...}} (only on clean shutdown)
   *   {"type":"end"}                           (only on clean shutdown)
   *
   * The values of the constants/event/polledData records use the same
   * structure as the corresponding parts of the single-JSON-document format.
   *
   * Returns null if |logFileContents| is not an NDJSON log.  Otherwise,
   * returns an object with a |logDump| in the same form as the
   * single-JSON-document format, and an |errorString| containing any
   * warnings.
   */
  function parseNdjsonDump_(logFileContents) {
    const logDump = {events: []};
    let sawFirstRecord = false;
    let sawEndRecord = false;

    for (let lineStart = 0; lineStart < logFileContents.length;) {
      let lineEnd = logFileContents.indexOf('\n', lineStart);
      if (lineEnd === -1) {
        lineEnd = logFileContents.length;
      }
      const line = logFileContents.substring(lineStart, lineEnd).trim();
      lineStart = lineEnd + 1;
      if (line === '') {
        continue;
      }

      let record = null;
      try {
        record = JSON.parse(line);
      } catch (error) {
        // If the very first line isn't a JSON record, this isn't an NDJSON
        // log at all.
        if (!sawFirstRecord) {
          return null;
        }
        // Otherwise the log was likely truncated mid-record (e.g. the browser
        // crashed).  Skip the incomplete line and stop; the missing end
        // record will add a truncation warning below.
        break;
      }

      if (typeof record !== 'object' || record === null ||
          typeof record.type !== 'string') {
        // NDJSON logs are identified by their first record having a "type"
        // field.  Anything else (e.g. a whole single-document dump on one
        // line) is some other format.
        if (!sawFirstRecord) {
          return null;
        }
        continue;
      }
      sawFirstRecord = true;

      switch (record.type) {
        case 'constants':
          if (logDump.constants === undefined &&
              typeof record.constants === 'object' &&
              record.constants !== null) {
            logDump.constants = record.constants;
          }
          break;
        case 'event':
          logDump.events.push(
              record.event !== null ? record.event : undefined);
          break;
        case 'polledData':
          if (typeof record.polledData === 'object' &&
              record.polledData !== null) {
            logDump.polledData = record.polledData;
          }
          break;
        case 'end':
          sawEndRecord = true;
          break;
        default:
          // Ignore unknown record types, for forward compatibility.
          break;
      }
    }

    if (!sawFirstRecord) {
      return null;
    }

    let errorString = '';
    if (!sawEndRecord) {
      // A cleanly written NDJSON log always ends with an end record.
      errorString += 'Log file truncated.  Events may be missing.\n';
    }
    return {logDump, errorString};
  }

  /**
   * Loads a log dump from the string |logFileContents|, which can be either a
   * full net-internals dump, or a NetLog dump only.  Returns a string
   * containing a log of the load.
   */
  function loadLogFile(logFileContents, fileName) {
    // NDJSON logs can't be parsed as a single JSON document, so try them
    // first.  This only looks at the first line, and leaves the other formats
    // to the code below.
    const ndjsonDump = parseNdjsonDump_(logFileContents);
    if (ndjsonDump !== null) {
      return ndjsonDump.errorString +
          loadLogDump(ndjsonDump.logDump, fileName);
    }

    // Try and parse the log dump as a single JSON string.  If this succeeds,
    // it's most likely a full log dump.  Otherwise, it may be a dump created by
    // --log-net-log.
    let parsedDump = null;
    let errorString = '';
    let parseError;
    try {
      parsedDump = JSON.parse(logFileContents);
    } catch (error) {
      parseError = error;
      try {
        // We may have a --log-net-log=blah log dump.  If so, remove the comma
        // after the final good entry, and add the necessary close brackets.
        const end = Math.max(
            logFileContents.lastIndexOf(',\n'),
            logFileContents.lastIndexOf(',\r'));
        if (end !== -1) {
          parsedDump = JSON.parse(logFileContents.substring(0, end) + ']}');
          errorString += 'Log file truncated.  Events may be missing.\n';
        }
      } catch (error2) {
      }
    }

    if (!parsedDump) {
      return 'Unable to parse log dump as JSON file: ' + parseError;
    }
    return errorString + loadLogDump(parsedDump, fileName);
  }

  // Exports.
  return {loadLogFile};
})();
