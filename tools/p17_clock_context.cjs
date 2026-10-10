// Supply the real dependency omitted by the unchanged isolated clock fixture.
// No mock replaces behavior or assertions; this loads the repository function.
'use strict';
const fs = require('fs'), path = require('path'), vm = require('vm');
const source = fs.readFileSync(path.join(__dirname, '../ui/web/app.js'), 'utf8');
const start = source.indexOf('function heroTimeoutAction(');
const end = source.indexOf('function paintActionClock()', start);
if (start < 0 || end <= start) throw new Error('Real clock dependency missing');
const create = vm.createContext;
vm.createContext = function(context, ...options) {
  const result = create.call(this, context, ...options);
  if (context.S && context.S.actionDeadlineMs && context.serverNow) {
    vm.runInContext(source.slice(start, end), result);
    if (result.heroTimeoutAction({legal:{fold:true}}) !== 'fold' ||
        result.heroTimeoutAction({legal:{check:true}}) !== 'check') {
      throw new Error('Actual legal timeout contract violated');
    }
  }
  return result;
};
