# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2020, 2021, 2024 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""REANA Workflow Controller interactive sessions REST API."""


from flask import Blueprint, jsonify, request
from webargs import fields
from webargs.flaskparser import use_kwargs

from reana_db.utils import _get_workflow_with_uuid_or_name
from reana_db.models import WorkflowSession, InteractiveSessionType, RunStatus

from reana_workflow_controller.workflow_run_manager import KubernetesWorkflowRunManager


blueprint = Blueprint("workflows_session", __name__)


@blueprint.route(
    "/workflows/<workflow_id_or_name>/open/<interactive_session_type>",
    methods=["POST"],
)
@use_kwargs({"user": fields.Str(required=True)}, location="query")
@use_kwargs({"image": fields.Str()}, location="json")
def open_interactive_session(
    workflow_id_or_name, interactive_session_type, user, **kwargs
):  # noqa
    r"""Start an interactive session inside the workflow workspace.

    ---
    post:
      summary: Start an interactive session inside the workflow workspace.
      description: >-
        This resource is expecting a workflow to start an interactive session
        within its workspace.
      operationId: open_interactive_session
      consumes:
        - application/json
      produces:
        - application/json
      parameters:
        - name: user
          in: query
          description: Required. UUID of workflow owner.
          required: true
          type: string
        - name: workflow_id_or_name
          in: path
          description: Required. Workflow UUID or name.
          required: true
          type: string
        - name: interactive_session_type
          in: path
          description: >-
            Optional. Type of interactive session to use, by default Jupyter
            Notebook.
          required: false
          type: string
        - name: interactive_session_configuration
          in: body
          description: >-
            Interactive session configuration.
          required: false
          schema:
            type: object
            properties:
              image:
                type: string
                description: >-
                  Replaces the default Docker image of an interactive session.
      responses:
        200:
          description: >-
            Request succeeded. The interactive session has been opened.
          schema:
            type: object
            properties:
              path:
                type: string
          examples:
            application/json:
              {
                "path": "/dd4e93cf-e6d0-4714-a601-301ed97eec60",
              }
        400:
          description: >-
            Request failed. The incoming data specification seems malformed.
          examples:
            application/json:
              {
                "message": "Malformed request."
              }
        404:
          description: >-
            Request failed. Either User or Workflow does not exist.
          examples:
            application/json:
              {
                "message": "Interactive session type terminl not found, try
                            with one of: [jupyter]"
              }
            application/json:
              {
                "message": "Workflow 256b25f4-4cfb-4684-b7a8-73872ef455a1
                            does not exist"
              }
        500:
          description: >-
            Request failed. Internal controller error.
    """
    try:
        if interactive_session_type not in InteractiveSessionType.__members__:
            error_msg = (
                f"Interactive session type {interactive_session_type} not found, "
                f"try with one of: {[e.name for e in InteractiveSessionType]}"
            )
            return jsonify({"message": error_msg}), 404

        workflow = _get_workflow_with_uuid_or_name(workflow_id_or_name, user_uuid=user)

        if workflow.sessions.first() is not None:
            return jsonify({"message": "Interactive session is already open"}), 404

        if workflow.status == RunStatus.deleted:
            error_msg = "Interactive session can't be opened from a deleted workflow"
            return jsonify({"message": error_msg}), 404

        kwrm = KubernetesWorkflowRunManager(workflow)
        access_path = kwrm.start_interactive_session(
            interactive_session_type,
            image=kwargs.get("image"),
        )
        return jsonify({"path": str(access_path)}), 200

    except (KeyError, ValueError) as e:
        status_code = 400 if workflow else 404
        return jsonify({"message": str(e)}), status_code
    except Exception as e:
        return jsonify({"message": str(e)}), 500


@blueprint.route("/workflows/<workflow_id_or_name>/close", methods=["POST"])
def close_interactive_session(workflow_id_or_name):  # noqa
    r"""Close an interactive workflow session.

    ---
    post:
      summary: Close an interactive workflow session.
      description: >-
        This resource is expecting a workflow to close an interactive session
        within its workspace.
      operationId: close_interactive_session
      consumes:
        - application/json
      produces:
        - application/json
      parameters:
        - name: user
          in: query
          description: Required. UUID of workflow owner.
          required: true
          type: string
        - name: workflow_id_or_name
          in: path
          description: Required. Workflow UUID or name.
          required: true
          type: string
      responses:
        200:
          description: >-
            Request succeeded. The interactive session has been closed.
          schema:
            type: object
            properties:
              message:
                type: string
          examples:
            application/json:
              {
                "message": "The interactive session has been closed",
              }
        400:
          description: >-
            Request failed. The incoming data specification seems malformed.
          examples:
            application/json:
              {
                "message": "Malformed request."
              }
        404:
          description: >-
            Request failed. Either User or Workflow does not exist.
          examples:
            application/json:
              {
                "message": "Workflow 256b25f4-4cfb-4684-b7a8-73872ef455a1
                            does not exist"
              }
        500:
          description: >-
            Request failed. Internal controller error.
    """
    try:
        user_uuid = request.args["user"]
        workflow = None
        workflow = _get_workflow_with_uuid_or_name(workflow_id_or_name, user_uuid)
        int_session = workflow.sessions.first()
        if not int_session:
            return (
                jsonify(
                    {
                        "message": "Workflow - {} has no open interactive session.".format(
                            workflow_id_or_name
                        )
                    }
                ),
                404,
            )
        kwrm = KubernetesWorkflowRunManager(workflow)
        kwrm.stop_interactive_session(int_session.id_)
        return jsonify({"message": "The interactive session has been closed"}), 200

    except (KeyError, ValueError) as e:
        status_code = 400 if workflow else 404
        return jsonify({"message": str(e)}), status_code
    except Exception as e:
        return jsonify({"message": str(e)}), 500
