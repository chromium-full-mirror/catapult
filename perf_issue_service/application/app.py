# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from flask import Flask, Response, jsonify

from application.api.dummy import dummy
from application.api.issues import issues
from application.api.alert_groups import alert_groups


class _PlainTextDefaultResponse(Response):
  # Backend API responses must not default to text/html when handlers return
  # plain error strings.
  default_mimetype = 'text/plain'


class _HardenedFlask(Flask):
  response_class = _PlainTextDefaultResponse

  def make_response(self, rv):
    # Catapult's vpython test environments run Flask < 2.2, where make_response
    # does not yet serialize list (or in 1.0, dict) payloads via app.json.
    if isinstance(rv, (dict, list)) and not hasattr(self, 'json'):
      rv = jsonify(rv)
    response = super().make_response(rv)
    if response.mimetype == 'text/html':
      response.mimetype = 'text/plain'
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('Content-Security-Policy',
                                "default-src 'none'; frame-ancestors 'none'")
    return response


def create_app():
  app = _HardenedFlask(__name__)
  app.register_blueprint(dummy, url_prefix='/')
  app.register_blueprint(issues, url_prefix='/issues')
  app.register_blueprint(alert_groups, url_prefix='/alert_groups')
  return app
