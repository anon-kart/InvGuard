// Source        : SCRUBD-CD (MSR 2025)
// Contract addr : 0x4e73b32ed6c35f570686b89848e5f39f20ecc106
// Target fn     : PRIVATE_ETH_CELL.Collect
// Original pragma: pragma solidity ^0.4.19;
// Original LOC  : 88
// Sub-contracts : 2 (PRIVATE_ETH_CELL, LogFile)
// Port report   : {"pragma_changed": true, "call_value_replaced": 1, "now_replaced": 1, "unnamed_fn_replaced": 1}

// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

contract PRIVATE_ETH_CELL
{
    mapping (address=>uint256) public balances;   

    uint public MinSum;

    LogFile Log;

    bool intitalized;

    function SetMinSum(uint _val)
    public
    {
        require(!intitalized);
        MinSum = _val;
    }

    function SetLogFile(address _log)
    public
    {
        require(!intitalized);
        Log = LogFile(_log);
    }

    function Initialized()
    public
    {
        intitalized = true;
    }

    function Deposit()
    public
    payable
    {
        balances[msg.sender]+= msg.value;
        Log.AddMessage(msg.sender,msg.value,"Put");
    }

    function Collect(uint _am)
    public
    payable
    {
        if(balances[msg.sender]>=MinSum && balances[msg.sender]>=_am)
        {
            (bool _callOk1, ) = msg.sender.call{value: _am}("");

            if (_callOk1)
            {
                balances[msg.sender]-=_am;
                Log.AddMessage(msg.sender,_am,"Collect");
            }
        }
    }

    receive() external payable {
        Deposit();
    }
}

contract LogFile
{
    struct Message
    {
        address Sender;
        string  Data;
        uint Val;
        uint  Time;
    }

    Message[] public History;

    Message LastMsg;

    function AddMessage(address _adr,uint _val,string memory _data)
    public
    {
        LastMsg.Sender = _adr;
        LastMsg.Time = block.timestamp;
        LastMsg.Val = _val;
        LastMsg.Data = _data;
        History.push(LastMsg);
    }
}
